#!/usr/bin/env python3
"""Experiment: LLM extraction time and accuracy vs image scale."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract_server"))

from grocery_extract.cursor_extractor import (
    current_extract_backend,
    default_extract_model,
    extract_products_from_image,
)
from grocery_extract.image_prep import _image_dimensions, resize_to_scale_percent
from grocery_extract.scoring import benchmark, score_image

DEFAULT_IMAGES = ["IMG_2027", "IMG_2030", "IMG_2061"]
DEFAULT_SCALES = [100, 75, 50, 40, 30, 25, 20]
DEFAULT_REPEATS = 2


def load_ground_truth() -> dict[str, list[dict]]:
    path = ROOT / "extract_server" / "tests" / "fixtures" / "ground_truth_products.json"
    payload = json.loads(path.read_text())
    return {k: [dict(p) for p in v] for k, v in payload.items()}


def find_jpg(image_id: str) -> Path | None:
    data_dir = ROOT / "data"
    for batch_dir in sorted(data_dir.glob("20*")):
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            return jpg
    return None


def run_experiment(
    *,
    image_ids: list[str],
    scales: list[int],
    repeats: int,
    out_dir: Path,
    api_key: str,
) -> dict:
    truth = load_ground_truth()
    out_dir.mkdir(parents=True, exist_ok=True)
    scaled_dir = out_dir / "scaled"
    logs_dir = out_dir / "logs"
    scaled_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    config = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image_ids": image_ids,
        "scales_pct": scales,
        "repeats": repeats,
        "model": default_extract_model(current_extract_backend()),
        "llm_max_dim": 0,
        "note": "llm_max_dim=0 sends the scaled JPEG as-is with no extra downscale",
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    runs: list[dict] = []
    total_calls = len(image_ids) * len(scales) * repeats
    call_num = 0

    for image_id in image_ids:
        source = find_jpg(image_id)
        if source is None:
            raise FileNotFoundError(f"Missing image {image_id}")
        orig_w, orig_h = _image_dimensions(source)
        orig_bytes = source.stat().st_size
        expected = truth.get(image_id, [])

        for scale_pct in scales:
            scaled_path = scaled_dir / image_id / f"scale_{scale_pct:03d}.jpg"
            width, height, file_bytes = resize_to_scale_percent(source, scale_pct, scaled_path)

            for repeat in range(1, repeats + 1):
                call_num += 1
                log_stem = f"{image_id}/scale_{scale_pct:03d}_rep{repeat}"
                raw_path = logs_dir / f"{log_stem}.raw.txt"
                json_path = logs_dir / f"{log_stem}.json"

                print(
                    f"[{call_num}/{total_calls}] {image_id} scale={scale_pct}% rep={repeat} "
                    f"({width}x{height}, {file_bytes/1024:.1f} KB)",
                    flush=True,
                )

                started = time.perf_counter()
                try:
                    products, raw = extract_products_from_image(
                        scaled_path,
                        api_key=api_key,
                        llm_max_dim=0,
                    )
                    elapsed = time.perf_counter() - started
                    rows = [p.to_product_dict() for p in products]
                    error = None
                except Exception as err:
                    elapsed = time.perf_counter() - started
                    rows = []
                    raw = ""
                    error = str(err)

                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(raw)
                image_score = score_image(image_id, expected, rows)
                record = {
                    "image_id": image_id,
                    "scale_pct": scale_pct,
                    "repeat": repeat,
                    "original_width": orig_w,
                    "original_height": orig_h,
                    "original_bytes": orig_bytes,
                    "scaled_width": width,
                    "scaled_height": height,
                    "scaled_bytes": file_bytes,
                    "llm_seconds": round(elapsed, 3),
                    "product_count": len(rows),
                    "expected_count": len(expected),
                    "recall": round(image_score.recall, 3),
                    "precision": round(image_score.precision, 3),
                    "f1": round(image_score.f1, 3),
                    "price_accuracy": round(
                        sum(1 for m in image_score.matches if m.expected and m.price_ok)
                        / max(1, sum(1 for m in image_score.matches if m.expected)),
                        3,
                    ),
                    "error": error,
                    "products": rows,
                    "raw_log": str(raw_path.relative_to(out_dir)),
                }
                json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                runs.append(record)

    summary = aggregate_results(runs, image_ids, scales)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(summary, out_dir))
    return summary


def aggregate_results(runs: list[dict], image_ids: list[str], scales: list[int]) -> dict:
    by_scale: dict[int, list[dict]] = defaultdict(list)
    for run in runs:
        if run.get("error"):
            continue
        by_scale[run["scale_pct"]].append(run)

    scale_rows = []
    for scale_pct in scales:
        bucket = by_scale.get(scale_pct, [])
        if not bucket:
            continue
        scale_rows.append(
            {
                "scale_pct": scale_pct,
                "mean_width": round(statistics.mean(r["scaled_width"] for r in bucket)),
                "mean_height": round(statistics.mean(r["scaled_height"] for r in bucket)),
                "mean_file_kb": round(statistics.mean(r["scaled_bytes"] for r in bucket) / 1024, 1),
                "mean_llm_seconds": round(statistics.mean(r["llm_seconds"] for r in bucket), 2),
                "stdev_llm_seconds": round(
                    statistics.pstdev(r["llm_seconds"] for r in bucket) if len(bucket) > 1 else 0,
                    2,
                ),
                "mean_recall": round(statistics.mean(r["recall"] for r in bucket), 3),
                "mean_f1": round(statistics.mean(r["f1"] for r in bucket), 3),
                "mean_price_accuracy": round(statistics.mean(r["price_accuracy"] for r in bucket), 3),
                "runs": len(bucket),
            }
        )

    per_image = {}
    for image_id in image_ids:
        image_runs = [r for r in runs if r["image_id"] == image_id and not r.get("error")]
        if not image_runs:
            continue
        actual_by_scale: dict[str, list[dict]] = {}
        truth = load_ground_truth()
        for scale_pct in scales:
            scale_runs = [r for r in image_runs if r["scale_pct"] == scale_pct]
            if scale_runs:
                actual_by_scale[str(scale_pct)] = scale_runs[-1]["products"]
        per_image[image_id] = {
            "expected_products": len(truth.get(image_id, [])),
            "by_scale": {},
        }
        for scale_pct in scales:
            scale_runs = [r for r in image_runs if r["scale_pct"] == scale_pct]
            if not scale_runs:
                continue
            per_image[image_id]["by_scale"][str(scale_pct)] = {
                "recall": round(statistics.mean(r["recall"] for r in scale_runs), 3),
                "f1": round(statistics.mean(r["f1"] for r in scale_runs), 3),
                "price_accuracy": round(statistics.mean(r["price_accuracy"] for r in scale_runs), 3),
                "llm_seconds": round(statistics.mean(r["llm_seconds"] for r in scale_runs), 2),
                "file_kb": round(statistics.mean(r["scaled_bytes"] for r in scale_runs) / 1024, 1),
            }

    baseline = next((row for row in scale_rows if row["scale_pct"] == 100), None)
    return {
        "images": image_ids,
        "scales_pct": scales,
        "total_runs": len(runs),
        "failed_runs": sum(1 for r in runs if r.get("error")),
        "by_scale": scale_rows,
        "per_image": per_image,
        "baseline_100pct": baseline,
    }


def render_markdown(summary: dict, out_dir: Path) -> str:
    lines = [
        "# LLM resize experiment",
        "",
        f"Output directory: `{out_dir}`",
        "",
        "## By scale (aggregated across images and repeats)",
        "",
        "| Scale % | WxH (avg) | File KB | LLM time (s) | Recall | F1 | Price acc |",
        "|--------:|----------:|--------:|-------------:|-------:|---:|----------:|",
    ]
    for row in summary["by_scale"]:
        lines.append(
            f"| {row['scale_pct']} | {row['mean_width']}x{row['mean_height']} | "
            f"{row['mean_file_kb']} | {row['mean_llm_seconds']} ± {row['stdev_llm_seconds']} | "
            f"{row['mean_recall']} | {row['mean_f1']} | {row['mean_price_accuracy']} |"
        )

    baseline = summary.get("baseline_100pct")
    if baseline:
        lines.extend(["", "## Accuracy loss vs 100% baseline", ""])
        for row in summary["by_scale"]:
            if row["scale_pct"] == 100:
                continue
            recall_delta = row["mean_recall"] - baseline["mean_recall"]
            f1_delta = row["mean_f1"] - baseline["mean_f1"]
            time_ratio = row["mean_llm_seconds"] / baseline["mean_llm_seconds"]
            size_ratio = row["mean_file_kb"] / baseline["mean_file_kb"]
            lines.append(
                f"- **{row['scale_pct']}%**: recall {recall_delta:+.3f}, f1 {f1_delta:+.3f}, "
                f"LLM time {time_ratio:.0%} of baseline, file size {size_ratio:.0%} of baseline"
            )

    lines.extend(["", "## Per-image detail", ""])
    for image_id, detail in summary.get("per_image", {}).items():
        lines.append(f"### {image_id} ({detail['expected_products']} expected products)")
        lines.append("")
        lines.append("| Scale % | Recall | F1 | LLM s |")
        lines.append("|--------:|-------:|---:|------:|")
        for scale, metrics in sorted(detail["by_scale"].items(), key=lambda x: int(x[0])):
            lines.append(
                f"| {scale} | {metrics['recall']:.3f} | {metrics['f1']:.3f} | {metrics['llm_seconds']:.2f} |"
            )
        lines.append("")

    lines.append("## Log files")
    lines.append("")
    lines.append("Raw LLM responses: `logs/<image_id>/scale_XXX_repN.raw.txt`")
    lines.append("Parsed run records: `logs/<image_id>/scale_XXX_repN.json`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM resize accuracy/speed experiment")
    parser.add_argument("--images", nargs="+", default=DEFAULT_IMAGES)
    parser.add_argument("--scales", nargs="+", type=int, default=DEFAULT_SCALES)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "extract_server" / "experiments" / "llm_resize_latest",
    )
    args = parser.parse_args()

    api_key = os.environ.get("CURSOR_API_KEY")
    if not api_key:
        print("CURSOR_API_KEY required", file=sys.stderr)
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_dir
    if out_dir.name == "llm_resize_latest":
        out_dir = out_dir.parent / f"llm_resize_{timestamp}"

    summary = run_experiment(
        image_ids=args.images,
        scales=args.scales,
        repeats=args.repeats,
        out_dir=out_dir,
        api_key=api_key,
    )
    print("\n" + render_markdown(summary, out_dir))
    print(f"\nWrote results to {out_dir}")
    return 0 if summary["failed_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
