import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helpers import (  # noqa: F401
    BENCHMARK_SUBSET,
    cache_path,
    find_jpg,
    ground_truth_by_image,
    load_cached,
    save_cache,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CACHE_DIR = Path(__file__).resolve().parents[1] / ".extract_cache"
_PROD_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "grocery.db"
_TEST_ROOT: Path | None = None


def pytest_configure(config):
    global _TEST_ROOT
    _TEST_ROOT = Path(tempfile.mkdtemp(prefix="grocery-test-"))
    os.environ["GROCERY_DB_PATH"] = str(_TEST_ROOT / "grocery.db")
    os.environ["GROCERY_DATA_DIR"] = str(_TEST_ROOT / "data")

    db_path = Path(os.environ["GROCERY_DB_PATH"]).resolve()
    if db_path == _PROD_DB_PATH.resolve():
        raise RuntimeError("Tests must not use the production grocery.db")


def pytest_sessionfinish(session, exitstatus):
    global _TEST_ROOT
    from extract_server.users_db import close_all_connections

    close_all_connections()
    if _TEST_ROOT is not None and _TEST_ROOT.exists():
        shutil.rmtree(_TEST_ROOT)
        _TEST_ROOT = None


@pytest.fixture(autouse=True)
def reset_db_connections():
    from extract_server.users_db import close_all_connections

    close_all_connections()
    yield
    close_all_connections()


@pytest.fixture(scope="session")
def api_key() -> str | None:
    return os.environ.get("CURSOR_API_KEY")


@pytest.fixture(scope="session")
def skip_without_api_key(api_key: str | None):
    if not api_key:
        pytest.skip("CURSOR_API_KEY not set")


@pytest.fixture(scope="session")
def app():
    from server import app

    return app


@pytest.fixture
def client(app):
    return TestClient(app)
