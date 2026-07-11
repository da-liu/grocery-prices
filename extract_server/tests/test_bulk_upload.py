from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from extract_server.db import is_valid_photo_id, new_photo_ids
from extract_server.extraction.ingest import accept_upload_batch


def test_new_photo_ids_returns_unique_uuid_ids():
    ids = new_photo_ids(3)
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert all(is_valid_photo_id(photo_id) for photo_id in ids)
    assert all(not photo_id.startswith("IMG_") for photo_id in ids)


def test_accept_upload_batch_assigns_distinct_image_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")

    from extract_server.db import init_db, register_user

    init_db()
    user = register_user("batchuser", "password12345")
    user_id = user.id
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)

    uploads = []
    for index in range(3):
        path = tmp_path / f"image-{index}.webp"
        path.write_bytes(f"RIFF....WEBP-{index}".encode())
        uploads.append(path)

    monkeypatch.setattr(
        "extract_server.extraction.ingest.user_photos_dir",
        lambda uid, date_folder: user_dir / "photos" / date_folder,
    )
    monkeypatch.setattr("extract_server.extraction.ingest.file_content_hash", lambda path: str(path))
    monkeypatch.setattr("extract_server.extraction.ingest.find_photo_by_content_hash", lambda *_args: None)
    monkeypatch.setattr(
        "extract_server.db.user_stores.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("extract_server.extraction.ingest.image_needs_store_label", lambda *_args: False)

    results = accept_upload_batch(uploads, user_id=user_id, max_workers=1, enqueue=False)

    assert len(results) == 3
    image_ids = [result["image_id"] for result in results]
    assert len(set(image_ids)) == 3
    assert all(is_valid_photo_id(image_id) for image_id in image_ids)
    assert all(result["extraction_status"] == "pending" for result in results)

    photos_root = user_dir / "photos"
    for upload_path, image_id in zip(uploads, image_ids, strict=True):
        webp_path = next(photos_root.glob(f"*/{image_id}.webp"))
        assert webp_path.exists()
        assert webp_path.suffix == ".webp"


def test_accept_upload_batch_persists_jpeg(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")

    from extract_server.db import init_db, register_user

    init_db()
    user = register_user("jpegbatch", "password12345")
    user_id = user.id
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)

    upload = tmp_path / "image-0.jpg"
    upload.write_bytes(b"\xff\xd8\xff jpeg-upload")

    monkeypatch.setattr(
        "extract_server.extraction.ingest.user_photos_dir",
        lambda uid, date_folder: user_dir / "photos" / date_folder,
    )
    monkeypatch.setattr("extract_server.extraction.ingest.file_content_hash", lambda path: str(path))
    monkeypatch.setattr("extract_server.extraction.ingest.find_photo_by_content_hash", lambda *_args: None)
    monkeypatch.setattr(
        "extract_server.db.user_stores.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("extract_server.extraction.ingest.image_needs_store_label", lambda *_args: False)

    results = accept_upload_batch([upload], user_id=user_id, max_workers=1, enqueue=False)

    assert len(results) == 1
    image_id = results[0]["image_id"]
    assert results[0]["extraction_status"] == "pending"

    photos_root = user_dir / "photos"
    jpg_path = next(photos_root.glob(f"*/{image_id}.jpg"))
    assert jpg_path.exists()
    assert jpg_path.read_bytes() == b"\xff\xd8\xff jpeg-upload"


def test_bulk_endpoint_passes_distinct_saved_paths(client, monkeypatch):
    reg = client.post(
        "/api/auth/register",
        json={"username": "bulk-uploader", "password": "password123"},
    )
    token = reg.json()["token"]
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    captured_bytes: list[bytes] = []

    def fake_batch(paths, **kwargs):
        captured_bytes.extend(path.read_bytes() for path in paths)
        return [
            {
                "image_id": f"photo-{i}",
                "products": [],
                "product_count": 0,
                "meta": {},
                "extractor": "cursor_sdk",
            }
            for i in range(len(paths))
        ]

    with patch("extract_server.api.routes.photos.accept_upload_batch", side_effect=fake_batch):
        resp = client.post(
            "/api/photos/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", ("image.jpg", b"photo-a", "image/jpeg")),
                ("files", ("image.jpg", b"photo-b", "image/jpeg")),
                ("files", ("image.jpg", b"photo-c", "image/jpeg")),
            ],
        )

    assert resp.status_code == 202, resp.text
    assert len(captured_bytes) == 3
    assert len(set(captured_bytes)) == 3
