from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from extract_server.extraction.worker import ExtractionJob
from extract_server.extraction.ingest import accept_upload_batch, run_extraction_pipeline


def test_accept_upload_batch_returns_pending_without_extraction(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")

    from extract_server.db import init_db, register_user
    from extract_server.db import get_extraction, get_photo

    init_db()
    user = register_user("async-user", "password12345")
    upload = tmp_path / "photo.webp"
    upload.write_bytes(b"RIFF....WEBP")

    monkeypatch.setattr(
        "extract_server.db.user_stores.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("extract_server.extraction.ingest.image_needs_store_label", lambda *_args: False)

    started = time.perf_counter()
    results = accept_upload_batch([upload], user_id=user.id, enqueue=False)
    accept_ms = (time.perf_counter() - started) * 1000

    assert len(results) == 1
    result = results[0]
    assert result["extraction_status"] == "pending"
    assert accept_ms < 5000
    photo = get_photo(user.id, result["image_id"])
    assert photo is not None
    assert photo["type"] is None
    assert get_extraction(user.id, result["image_id"]) is None


def test_run_extraction_pipeline_completes_photo(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")

    from extract_server.db import init_db, register_user
    from extract_server.db import get_extraction, get_photo

    init_db()
    user = register_user("extract-user", "password12345")
    upload = tmp_path / "photo.webp"
    upload.write_bytes(b"RIFF....WEBP")

    monkeypatch.setattr(
        "extract_server.db.user_stores.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("extract_server.extraction.ingest.image_needs_store_label", lambda *_args: False)

    accepted = accept_upload_batch([upload], user_id=user.id, enqueue=False)[0]
    photo = get_photo(user.id, accepted["image_id"])
    assert photo is not None
    date_folder = photo["blob_key"].split("/")[-2]
    job = ExtractionJob(
        user_id=user.id,
        image_id=accepted["image_id"],
        api_key="test",
        user_stores=[],
        exif={},
        date_folder=date_folder,
        content_hash=photo["content_hash"],
    )

    def fake_extract(upload_path: Path, **kwargs):
        from extract_server.extraction.schema import ExtractionResult, ExtractedProduct, ExtractionTiming

        return ExtractionResult(
            image_path=str(upload_path),
            products=[
                ExtractedProduct(product_name="Milk", price=4.99, category="dairy"),
            ],
            photo_type="shelf",
            raw_response='{"type":"shelf","products":[{"product_name":"Milk","price":4.99,"category":"dairy"}]}',
            extractor="gemini_direct",
            timing=ExtractionTiming(llm_ms=2000, other_ms=50, model="auto"),
        )

    monkeypatch.setattr("extract_server.extraction.ingest.extract_from_upload", fake_extract)
    monkeypatch.setattr("extract_server.extraction.match_catalog.match_photo", lambda *_args, **_kwargs: None)

    result = run_extraction_pipeline(job)
    assert result["extraction_status"] == "done"
    assert result.get("status") == "matched"
    assert result["product_count"] == 1

    extraction = get_extraction(user.id, accepted["image_id"])
    assert extraction is not None
    assert extraction.get("extraction_error") is None
    assert extraction.get("status") == "matched"
    assert extraction["llm_ms"] == 2000
    assert extraction["other_ms"] == 50
    assert extraction["model"] == "auto"

    photo = get_photo(user.id, accepted["image_id"])
    assert photo is not None
    assert photo["type"] == "shelf"


def test_photos_status_endpoint(client, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")

    from extract_server.db import close_all_connections, init_db

    close_all_connections()
    init_db()

    reg = client.post(
        "/api/auth/register",
        json={"username": "status-user", "password": "password123"},
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("extract_server.api.routes.photos.accept_upload_batch") as accept:
        accept.return_value = [
            {
                "image_id": "IMG_0001",
                "extraction_status": "pending",
                "product_count": 0,
            }
        ]
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            upload = client.post(
                "/api/photos/bulk",
                headers=headers,
                files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
            )
    assert upload.status_code == 202

    status = client.post(
        "/api/photos/status",
        headers=headers,
        json={"ids": ["IMG_0001"]},
    )
    assert status.status_code == 200
