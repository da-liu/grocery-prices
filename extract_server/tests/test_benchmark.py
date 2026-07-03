from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grocery_extract.cursor_extractor import extract_products_from_image  # noqa: E402
from grocery_extract.scoring import benchmark  # noqa: E402
from helpers import BENCHMARK_SUBSET, find_jpg, ground_truth_by_image, load_cached, save_cache

# Targets calibrated against manual extractions in ground_truth_products.json
MIN_RECALL = 0.75
MIN_F1 = 0.70
MIN_PRICE_ACCURACY = 0.80
MIN_CATEGORY_ACCURACY = 0.70


def _extract(image_id: str, api_key: str, use_cache: bool = True) -> list[dict]:
    cached = load_cached(image_id) if use_cache else None
    if cached is not None:
        return cached

    jpg = find_jpg(image_id)
    assert jpg is not None, f"Missing JPG for {image_id}"

    products, raw = extract_products_from_image(jpg, api_key=api_key)
    rows = [p.to_product_dict() for p in products]
    save_cache(image_id, rows, raw)
    return rows


@pytest.mark.integration
def test_extract_single_image(skip_without_api_key, api_key: str):
    rows = _extract("IMG_2060", api_key)
    assert len(rows) >= 1
    assert rows[0]["product_name"]
    assert rows[0]["category"]


@pytest.mark.integration
def test_benchmark_subset(skip_without_api_key, api_key: str):
    truth = ground_truth_by_image()
    actual: dict[str, list[dict]] = {}
    for image_id in BENCHMARK_SUBSET:
        actual[image_id] = _extract(image_id, api_key)

    report = benchmark({k: truth[k] for k in BENCHMARK_SUBSET}, actual)
    summary = report.summary()

    report_path = Path(__file__).resolve().parents[1] / "benchmark_subset.json"
    report_path.write_text(json.dumps(summary, indent=2) + "\n")

    failures = []
    for score in report.image_scores:
        if score.recall < 0.5:
            failures.append(f"{score.image_id}: recall={score.recall:.2f}")

    print("\nBenchmark subset:", json.dumps(summary, indent=2))
    if failures:
        print("Low-recall images:", failures)

    assert summary["mean_recall"] >= MIN_RECALL, summary
    assert summary["mean_f1"] >= MIN_F1, summary
    assert summary["price_accuracy"] >= MIN_PRICE_ACCURACY, summary
    assert summary["category_accuracy"] >= MIN_CATEGORY_ACCURACY, summary


@pytest.mark.integration
@pytest.mark.slow
def test_benchmark_full(skip_without_api_key, api_key: str):
    if os.environ.get("GROCERY_BENCHMARK_FULL") != "1":
        pytest.skip("Set GROCERY_BENCHMARK_FULL=1 to run full 45-image benchmark")

    truth = ground_truth_by_image()
    actual = {image_id: _extract(image_id, api_key) for image_id in sorted(truth)}
    report = benchmark(truth, actual)
    summary = report.summary()

    report_path = Path(__file__).resolve().parents[1] / "benchmark_full.json"
    report_path.write_text(json.dumps(summary, indent=2) + "\n")
    print("\nBenchmark full:", json.dumps(summary, indent=2))

    assert summary["mean_recall"] >= MIN_RECALL, summary
    assert summary["mean_f1"] >= MIN_F1, summary
