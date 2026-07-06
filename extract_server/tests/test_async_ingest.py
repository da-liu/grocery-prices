from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

from grocery_extract.extract_worker import ExtractionJob
from grocery_extract.ingest import accept_upload, run_extraction


def test_accept_upload_returns_pending_without_extraction(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user
    from grocery_extract.catalog_db import get_photo

    init_db()
    user = register_user("async-user", "password12345")
    upload = tmp_path / "photo.webp"
    upload.write_bytes(b"RIFF....WEBP")

    monkeypatch.setattr(
        "grocery_extract.user_stores_db.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("grocery_extract.ingest.image_needs_store_label", lambda *_args: False)

    started = time.perf_counter()
    result = accept_upload(upload, user_id=user.id, source="upload")
    accept_ms = (time.perf_counter() - started) * 1000

    assert result["extraction_status"] == "pending"
    assert accept_ms < 5000
    photo = get_photo(user.id, result["image_id"])
    assert photo is not None
    from grocery_extract.catalog_db import get_extraction

    assert get_extraction(user.id, result["image_id"]) is None


def test_run_extraction_completes_photo(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user
    from grocery_extract.catalog_db import get_extraction, get_photo

    init_db()
    user = register_user("extract-user", "password12345")
    upload = tmp_path / "photo.webp"
    upload.write_bytes(b"RIFF....WEBP")

    monkeypatch.setattr(
        "grocery_extract.user_stores_db.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("grocery_extract.ingest.image_needs_store_label", lambda *_args: False)

    accepted = accept_upload(upload, user_id=user.id, source="upload")
    job = ExtractionJob(
        user_id=user.id,
        image_id=accepted["image_id"],
        source="upload",
        api_key="test",
        existing_products=[],
        user_stores=[],
        exif={},
        date_folder=accepted["date_folder"],
        captured_at=None,
        store_location_id=None,
        content_hash=accepted["content_hash"],
    )

    def fake_extract(upload_path: Path, **kwargs):
        from grocery_extract.schema import ExtractionResult, ExtractedProduct, ExtractionTiming, ImageMeta

        return ExtractionResult(
            image_path=str(upload_path),
            meta=ImageMeta(image_id=kwargs["image_id"], source_file=str(upload_path)),
            products=[
                ExtractedProduct(product_name="Milk", price=4.99, category="dairy"),
            ],
            photo_type="shelf",
            raw_response='{"type":"shelf","products":[{"product_name":"Milk","price":4.99,"category":"dairy"}]}',
            extractor="cursor_sdk",
            timing=ExtractionTiming(llm_ms=2000, other_ms=50, model="auto"),
        )

    monkeypatch.setattr("grocery_extract.ingest.extract_from_upload", fake_extract)

    result = run_extraction(job)
    assert result["extraction_status"] == "done"
    assert result["product_count"] == 1

    extraction = get_extraction(user.id, accepted["image_id"])
    assert extraction is not None
    assert extraction.get("extraction_error") is None
    assert extraction["llm_ms"] == 2000
    assert extraction["other_ms"] == 50
    assert extraction["model"] == "auto"

    photo = get_photo(user.id, accepted["image_id"])
    assert photo is not None
    assert photo["type"] == "shelf"


def test_photos_status_endpoint(client, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    reg = client.post(
        "/api/auth/register",
        json={"username": "status-user", "password": "password123"},
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("server.accept_upload_batch") as accept:
        accept.return_value = [
            {
                "image_id": "IMG_0001",
                "extraction_status": "pending",
                "products": [],
                "product_count": 0,
                "meta": {},
            }
        ]
        with patch.dict("os.environ", {"CURSOR_API_KEY": "test-key"}):
            upload = client.post(
                "/api/photos/bulk",
                headers=headers,
                files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
                data={"source": "upload"},
            )
    assert upload.status_code == 202

    status = client.post(
        "/api/photos/status",
        headers=headers,
        json={"ids": ["IMG_0001"]},
    )
    assert status.status_code == 200
