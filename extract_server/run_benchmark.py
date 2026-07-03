import json
import os
import sys
from pathlib import Path

GROCERY_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent / "tests"
sys.path.insert(0, str(GROCERY_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from helpers import BENCHMARK_SUBSET, find_jpg, ground_truth_by_image, load_cached, save_cache
from grocery_extract.cursor_extractor import extract_products_from_image
from grocery_extract.scoring import benchmark

MIN_RECALL = 0.75
MIN_F1 = 0.70
MIN_PRICE_ACCURACY = 0.80
MIN_CATEGORY_ACCURACY = 0.70


def _extract(image_id: str, api_key: str, use_cache: bool = True) -> list[dict]:
    cached = load_cached(image_id) if use_cache else None
    if cached is not None:
        return cached

    jpg = find_jpg(image_id)
    if jpg is None:
        raise FileNotFoundError(image_id)

    products, raw = extract_products_from_image(jpg, api_key=api_key)
    rows = [p.to_product_dict() for p in products]
    save_cache(image_id, rows, raw)
    return rows


def main() -> int:
    api_key = os.environ.get("CURSOR_API_KEY")
    if not api_key:
        print("CURSOR_API_KEY required", file=sys.stderr)
        return 1

    subset = BENCHMARK_SUBSET
    if os.environ.get("GROCERY_BENCHMARK_FULL") == "1":
        subset = sorted(ground_truth_by_image())

    truth = ground_truth_by_image()
    actual = {image_id: _extract(image_id, api_key) for image_id in subset}
    report = benchmark({k: truth[k] for k in subset}, actual)
    summary = report.summary()

    out = Path(__file__).resolve().parents[1] / (
        "benchmark_full.json" if len(subset) > len(BENCHMARK_SUBSET) else "benchmark_subset.json"
    )
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))

    ok = (
        summary["mean_recall"] >= MIN_RECALL
        and summary["mean_f1"] >= MIN_F1
        and summary["price_accuracy"] >= MIN_PRICE_ACCURACY
        and summary["category_accuracy"] >= MIN_CATEGORY_ACCURACY
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
