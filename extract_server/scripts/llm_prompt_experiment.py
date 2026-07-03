#!/usr/bin/env python3
"""Compare extraction prompt variants on 30% scaled shelf photos."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
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
from prompt_variants import PROMPT_VARIANTS  # noqa: E402
from vision_runner import run_cursor_vision  # noqa: E402

DEFAULT_VARIANTS = ["baseline", "concise", "ocr_focus", "minimal_schema"]
DEFAULT_MODEL = "composer-2.5"


def render_markdown(summary: dict, out_dir: Path) -> str:
    lines = [
        "# LLM prompt variant experiment",
        "",
        f"Output: `{out_dir}`",
        f"Model: {summary['model']}",
        f"Scale: {summary['scale_pct']}%",
        f"Repeats: {summary['repeats']}",
        "",
        "| Variant | LLM s | Recall | F1 | Price acc | vs baseline F1 |",
        "|---------|------:|-------:|---:|----------:|---------------:|",
    ]
    baseline_f1 = next(
        (row["mean_f1"] for row in summary["by_variant"] if row["variant"] == "baseline"),
        None,
    )
    for row in summary["by_variant"]:
        delta = ""
        if baseline_f1 is not None and row["variant"] != "baseline":
            delta = f"{row['mean_f1'] - baseline_f1:+.3f}"
        elif row["variant"] == "baseline":
            delta = "—"
        lines.append(
            f"| {row['variant']} | {row['mean_llm_seconds']} ± {row['stdev_llm_seconds']} "
            f"| {row['mean_recall']} | {row['mean_f1']} | {row['mean_price_accuracy']} | {delta} |"
        )
    lines.extend(["", "## Logs", "", "`logs/<image_id>/<variant>_repN`"])
    return "\n".join(lines) + "\n"


def run_experiment(
    *,
    image_ids: list[str],
    variants: list[str],
    model: str,
    scale_pct: int,
    repeats: int,
    out_dir: Path,
) -> dict:
    truth = load_ground_truth()
    out_dir.mkdir(parents=True, exist_ok=True)
    scaled_dir = out_dir / "scaled"
    logs_dir = out_dir / "logs"
    prompts_dir = out_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    for name, text in PROMPT_VARIANTS.items():
        if name in variants:
            (prompts_dir / f"{name}.txt").write_text(text)

    config = {
        "created_at": utc_now(),
        "experiment": "llm_prompt_variants",
        "image_ids": image_ids,
        "variants": variants,
        "model": model,
        "scale_pct": scale_pct,
        "repeats": repeats,
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    runs: list[dict] = []
    total = len(image_ids) * len(variants) * repeats
    n = 0

    for image_id in image_ids:
        source = find_jpg(image_id)
        if source is None:
            raise FileNotFoundError(image_id)
        scaled = scaled_image_path(source, scale_pct, scaled_dir, image_id)
        file_kb = scaled.stat().st_size / 1024

        for variant in variants:
            prompt = PROMPT_VARIANTS[variant]
            for repeat in range(1, repeats + 1):
                n += 1
                stem = f"{image_id}/{variant}_rep{repeat}"
                print(f"[{n}/{total}] {image_id} variant={variant} rep={repeat}", flush=True)

                record = {
                    "image_id": image_id,
                    "variant": variant,
                    "model": model,
                    "repeat": repeat,
                    "scale_pct": scale_pct,
                    "file_kb": round(file_kb, 1),
                }
                try:
                    products, raw, elapsed = run_cursor_vision(
                        scaled, prompt=prompt, model=model
                    )
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

                write_run_log(logs_dir, stem, record, raw)
                runs.append(record)

    by_variant: dict[str, list[dict]] = {}
    for run in runs:
        if run.get("error"):
            continue
        by_variant.setdefault(run["variant"], []).append(run)

    rows = []
    for variant in variants:
        bucket = by_variant.get(variant, [])
        if not bucket:
            continue
        rows.append(
            {
                "variant": variant,
                "runs": len(bucket),
                "mean_llm_seconds": round(statistics.mean(r["llm_seconds"] for r in bucket), 2),
                "stdev_llm_seconds": round(
                    statistics.pstdev(r["llm_seconds"] for r in bucket) if len(bucket) > 1 else 0,
                    2,
                ),
                "mean_recall": round(statistics.mean(r["recall"] for r in bucket), 3),
                "mean_f1": round(statistics.mean(r["f1"] for r in bucket), 3),
                "mean_price_accuracy": round(statistics.mean(r["price_accuracy"] for r in bucket), 3),
            }
        )

    summary = {
        "model": model,
        "scale_pct": scale_pct,
        "repeats": repeats,
        "total_runs": len(runs),
        "failed_runs": sum(1 for r in runs if r.get("error")),
        "by_variant": rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(summary, out_dir))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare extraction prompt variants")
    parser.add_argument("--images", nargs="+", default=DEFAULT_IMAGES)
    parser.add_argument("--variants", nargs="+", default=DEFAULT_VARIANTS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE_PCT)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "extract_server" / "experiments" / "llm_prompt_latest",
    )
    args = parser.parse_args()

    if not os.environ.get("CURSOR_API_KEY"):
        print("CURSOR_API_KEY required", file=sys.stderr)
        return 1

    out_dir = args.out_dir
    if out_dir.name == "llm_prompt_latest":
        out_dir = out_dir.parent / f"llm_prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    summary = run_experiment(
        image_ids=args.images,
        variants=args.variants,
        model=args.model,
        scale_pct=args.scale,
        repeats=args.repeats,
        out_dir=out_dir,
    )
    print((out_dir / "summary.md").read_text())
    print(f"Wrote results to {out_dir}")
    return 0 if summary["failed_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
