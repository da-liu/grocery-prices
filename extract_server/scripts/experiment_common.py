"""Shared helpers for LLM extraction experiments."""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_PATH = ROOT / "extract_server" / "tests" / "fixtures" / "ground_truth_products.json"
DEFAULT_SCALE_PCT = 30
DEFAULT_IMAGES = ["IMG_2027", "IMG_2030", "IMG_2061"]


def load_ground_truth() -> dict[str, list[dict]]:
    payload = json.loads(GROUND_TRUTH_PATH.read_text())
    return {k: [dict(p) for p in v] for k, v in payload.items()}


def find_jpg(image_id: str) -> Path | None:
    """Locate a shelf photo for an image id (jpg subfolder or batch HEIC/JPEG)."""
    data_dir = ROOT / "data"
    candidates: list[Path] = []
    for batch_dir in sorted(data_dir.glob("20*")):
        candidates.extend(
            [
                batch_dir / "jpg" / f"{image_id}.jpg",
                batch_dir / f"{image_id}.jpg",
                batch_dir / f"{image_id}.HEIC",
                batch_dir / f"{image_id}.heic",
            ]
        )
    test_dir = data_dir / "test-data"
    if test_dir.is_dir():
        candidates.extend(
            [
                test_dir / f"{image_id}.jpg",
                test_dir / f"{image_id}.HEIC",
                test_dir / f"{image_id}.heic",
            ]
        )
    for path in candidates:
        if path.exists():
            return path
    return None


def scaled_image_path(source: Path, scale_pct: int, out_dir: Path, image_id: str) -> Path:
    from grocery_extract.image_prep import resize_to_scale_percent

    dest = out_dir / image_id / f"scale_{scale_pct:03d}.jpg"
    if not dest.exists():
        resize_to_scale_percent(source, scale_pct, dest)
    return dest


def write_run_log(
    logs_dir: Path,
    stem: str,
    record: dict,
    raw: str,
) -> None:
    path = logs_dir / stem
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / f"{path.name}.raw.txt").write_text(raw)
    (path.parent / f"{path.name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


def score_run(image_id: str, products: list[dict], truth: dict[str, list[dict]]) -> dict:
    from grocery_extract.scoring import score_image

    expected = truth.get(image_id, [])
    image_score = score_image(image_id, expected, products)
    price_pairs = [m for m in image_score.matches if m.expected and m.actual is not None]
    return {
        "expected_count": len(expected),
        "product_count": len(products),
        "recall": round(image_score.recall, 3),
        "precision": round(image_score.precision, 3),
        "f1": round(image_score.f1, 3),
        "price_accuracy": round(
            sum(1 for m in price_pairs if m.price_ok) / max(1, len(price_pairs)),
            3,
        ),
    }


def aggregate_runs(runs: list[dict], group_key: str) -> list[dict]:
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        if run.get("error"):
            continue
        buckets[str(run[group_key])].append(run)

    rows = []
    for key, bucket in sorted(buckets.items(), key=lambda item: item[0]):
        rows.append(
            {
                group_key: key,
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
    return rows


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
