#!/usr/bin/env python3
"""Compare vision models on 30% scaled shelf photos."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract_server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from experiment_common import (  # noqa: E402
    DEFAULT_IMAGES,
    DEFAULT_SCALE_PCT,
    find_jpg,
    load_ground_truth,
    scaled_image_path,
    score_run,
    utc_now,
    write_run_log,
)
from grocery_extract.prompt import build_prompt  # noqa: E402
from vision_runner import run_cursor_vision, run_gemini_direct  # noqa: E402

# Production baseline + user-selected Gemini models.
DEFAULT_MODELS = [
    ("composer-2.5", "cursor"),
    ("gemini-2.5-flash", "cursor"),
    ("gemini-2.5-flash", "gemini_direct"),
    ("gemini-3-flash", "cursor"),
    ("gemini-3-flash", "gemini_direct"),
]


def render_markdown(summary: dict, out_dir: Path) -> str:
    lines = [
        "# LLM model comparison experiment",
        "",
        f"Output: `{out_dir}`",
        f"Scale: {summary['scale_pct']}% of original max dimension",
        f"Repeats: {summary['repeats']}",
        "",
        "| Model | Backend | LLM s | Recall | F1 | Price acc | File KB |",
        "|-------|---------|------:|-------:|---:|----------:|--------:|",
    ]
    for row in summary["by_model_backend"]:
        lines.append(
            f"| {row['model']} | {row['backend']} | {row['mean_llm_seconds']} ± {row['stdev_llm_seconds']} "
            f"| {row['mean_recall']} | {row['mean_f1']} | {row['mean_price_accuracy']} | {row['mean_file_kb']} |"
        )
    lines.extend(["", "## Skipped backends", ""])
    for note in summary.get("notes", []):
        lines.append(f"- {note}")
    lines.extend(["", "## Logs", "", "`logs/<image_id>/<model>__<backend>_repN`"])
    return "\n".join(lines) + "\n"


def run_experiment(
    *,
    image_ids: list[str],
    models: list[tuple[str, str]],
    scale_pct: int,
    repeats: int,
    out_dir: Path,
) -> dict:
    truth = load_ground_truth()
    out_dir.mkdir(parents=True, exist_ok=True)
    scaled_dir = out_dir / "scaled"
    logs_dir = out_dir / "logs"
    prompt = build_prompt()
    notes: list[str] = []

    config = {
        "created_at": utc_now(),
        "experiment": "llm_model_comparison",
        "image_ids": image_ids,
        "scale_pct": scale_pct,
        "repeats": repeats,
        "models": [{"model": m, "backend": b} for m, b in models],
        "prompt": "baseline (build_prompt)",
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    runs: list[dict] = []
    total = len(image_ids) * len(models) * repeats
    n = 0

    for image_id in image_ids:
        source = find_jpg(image_id)
        if source is None:
            raise FileNotFoundError(image_id)
        scaled = scaled_image_path(source, scale_pct, scaled_dir, image_id)
        file_kb = scaled.stat().st_size / 1024

        for model, backend in models:
            for repeat in range(1, repeats + 1):
                n += 1
                stem = f"{image_id}/{model}__{backend}_rep{repeat}"
                print(f"[{n}/{total}] {image_id} model={model} backend={backend} rep={repeat}", flush=True)

                record = {
                    "image_id": image_id,
                    "model": model,
                    "backend": backend,
                    "repeat": repeat,
                    "scale_pct": scale_pct,
                    "file_kb": round(file_kb, 1),
                }

                try:
                    if backend == "cursor":
                        products, raw, elapsed = run_cursor_vision(
                            scaled, prompt=prompt, model=model
                        )
                    elif backend == "gemini_direct":
                        products, raw, elapsed = run_gemini_direct(
                            scaled, prompt=prompt, model=model
                        )
                    else:
                        raise ValueError(f"Unknown backend: {backend}")

                    record.update(score_run(image_id, products, truth))
                    record["llm_seconds"] = round(elapsed, 3)
                    record["products"] = products
                    record["error"] = None
                except Exception as err:
                    raw = ""
                    record["error"] = str(err)
                    record["llm_seconds"] = 0
                    record["products"] = []
                    record.update(
                        {
                            "expected_count": len(truth.get(image_id, [])),
                            "product_count": 0,
                            "recall": 0,
                            "precision": 0,
                            "f1": 0,
                            "price_accuracy": 0,
                        }
                    )
                    if backend == "gemini_direct" and "GEMINI" in str(err).upper():
                        notes.append(f"gemini_direct skipped/failed: {err}")

                write_run_log(logs_dir, stem, record, raw)
                runs.append(record)

    by_key: dict[str, list[dict]] = {}
    for run in runs:
        if run.get("error"):
            continue
        key = f"{run['model']}::{run['backend']}"
        by_key.setdefault(key, []).append(run)

    by_model_backend = []
    for key, bucket in sorted(by_key.items()):
        model, backend = key.split("::", 1)
        import statistics

        by_model_backend.append(
            {
                "model": model,
                "backend": backend,
                "runs": len(bucket),
                "mean_llm_seconds": round(statistics.mean(r["llm_seconds"] for r in bucket), 2),
                "stdev_llm_seconds": round(
                    statistics.pstdev(r["llm_seconds"] for r in bucket) if len(bucket) > 1 else 0,
                    2,
                ),
                "mean_recall": round(statistics.mean(r["recall"] for r in bucket), 3),
                "mean_f1": round(statistics.mean(r["f1"] for r in bucket), 3),
                "mean_price_accuracy": round(statistics.mean(r["price_accuracy"] for r in bucket), 3),
                "mean_file_kb": round(statistics.mean(r["file_kb"] for r in bucket), 1),
            }
        )

    summary = {
        "scale_pct": scale_pct,
        "repeats": repeats,
        "total_runs": len(runs),
        "failed_runs": sum(1 for r in runs if r.get("error")),
        "by_model_backend": by_model_backend,
        "notes": sorted(set(notes)),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(summary, out_dir))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare vision models at fixed image scale")
    parser.add_argument("--images", nargs="+", default=DEFAULT_IMAGES)
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE_PCT)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "extract_server" / "experiments" / "llm_model_latest",
    )
    args = parser.parse_args()

    if not os.environ.get("CURSOR_API_KEY"):
        print("CURSOR_API_KEY required", file=sys.stderr)
        return 1

    out_dir = args.out_dir
    if out_dir.name == "llm_model_latest":
        from datetime import datetime

        out_dir = out_dir.parent / f"llm_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    summary = run_experiment(
        image_ids=args.images,
        models=DEFAULT_MODELS,
        scale_pct=args.scale,
        repeats=args.repeats,
        out_dir=out_dir,
    )
    print((out_dir / "summary.md").read_text())
    print(f"Wrote results to {out_dir}")
    return 0 if summary["failed_runs"] < summary["total_runs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
