import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from server import app  # noqa: E402
from helpers import find_jpg  # noqa: E402


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.integration
def test_extract_endpoint(skip_without_api_key, api_key: str, monkeypatch):
    monkeypatch.setenv("CURSOR_API_KEY", api_key)
    jpg = find_jpg("IMG_2060")
    assert jpg is not None

    client = TestClient(app)
    with jpg.open("rb") as f:
        resp = client.post("/extract", files={"file": (jpg.name, f, "image/jpeg")})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["extractor"] == "cursor_sdk"
    assert len(body["products"]) >= 1
    assert body["products"][0]["product_name"]
