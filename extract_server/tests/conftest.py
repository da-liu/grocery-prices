import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_products import PRODUCTS  # noqa: E402

CACHE_DIR = Path(__file__).resolve().parents[1] / ".extract_cache"
DATA_DIR = ROOT / "data"

# Representative subset for fast iteration (mix of stores and product counts)
BENCHMARK_SUBSET = [
    "IMG_2027",
    "IMG_2030",
    "IMG_2044",
    "IMG_2053",
    "IMG_2058",
    "IMG_2061",
    "IMG_2065",
    "IMG_2071",
]


def ground_truth_by_image() -> dict[str, list[dict]]:
    return {k: [dict(p) for p in v] for k, v in PRODUCTS.items()}


def find_jpg(image_id: str) -> Path | None:
    for batch_dir in sorted(DATA_DIR.glob("20*")):
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            return jpg
    legacy = DATA_DIR / "jpg" / f"{image_id}.jpg"
    return legacy if legacy.exists() else None


def cache_path(image_id: str) -> Path:
    return CACHE_DIR / f"{image_id}.json"


def load_cached(image_id: str) -> list[dict] | None:
    path = cache_path(image_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return payload.get("products")


def save_cache(image_id: str, products: list[dict], raw: str | None = None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(image_id).write_text(
        json.dumps({"products": products, "raw_response": raw}, ensure_ascii=False, indent=2)
        + "\n"
    )


@pytest.fixture(scope="session")
def api_key() -> str | None:
    import os

    return os.environ.get("CURSOR_API_KEY")


@pytest.fixture(scope="session")
def skip_without_api_key(api_key: str | None):
    if not api_key:
        pytest.skip("CURSOR_API_KEY not set")
