import os
from pathlib import Path

import pytest

from helpers import (  # noqa: F401
    BENCHMARK_SUBSET,
    cache_path,
    find_jpg,
    ground_truth_by_image,
    load_cached,
    save_cache,
)

CACHE_DIR = Path(__file__).resolve().parents[1] / ".extract_cache"


@pytest.fixture(scope="session")
def api_key() -> str | None:
    return os.environ.get("CURSOR_API_KEY")


@pytest.fixture(scope="session")
def skip_without_api_key(api_key: str | None):
    if not api_key:
        pytest.skip("CURSOR_API_KEY not set")
