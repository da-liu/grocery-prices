from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from grocery_extract.catalog_db import allocate_image_ids, next_image_id
from grocery_extract.ingest import accept_upload_batch


def test_allocate_image_ids_returns_unique_sequential_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user
    from grocery_extract.catalog_db import save_photo_ingest

    init_db()
    user = register_user("bulkuser", "password12345")
    user_id = user.id
    original, jpeg = (
        f"users/{user_id}/photos/2026_07_02/IMG_0003.HEIC",
        f"users/{user_id}/photos/2026_07_02/jpg/IMG_0003.jpg",
    )
    save_photo_ingest(
        user_id,
        photo_id="IMG_0003",
        photo_type="shelf",
        original_blob_key=original,
        jpeg_blob_key=jpeg,
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at=None,
        store_location_id=None,
        extractor="cursor_sdk",
        raw_response=None,
        products=[],
    )

    ids = allocate_image_ids(user_id, 3)
    assert ids == ["IMG_0004", "IMG_0005", "IMG_0006"]
    assert next_image_id(user_id) == "IMG_0007"


def test_ingest_upload_batch_assigns_distinct_image_ids(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user

    init_db()
    user = register_user("batchuser", "password12345")
    user_id = user.id
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)

    uploads = []
    for index in range(3):
        path = tmp_path / f"image-{index}.jpg"
        path.write_bytes(f"photo-{index}".encode())
        uploads.append(path)

    monkeypatch.setattr(
        "grocery_extract.ingest.user_photos_dir",
        lambda uid, date_folder: user_dir / "photos" / date_folder,
    )
    monkeypatch.setattr("grocery_extract.ingest.file_content_hash", lambda path: path.read_bytes().decode())
    monkeypatch.setattr("grocery_extract.ingest.find_photo_by_content_hash", lambda *_args: None)
    monkeypatch.setattr("grocery_extract.ingest.extract_exif", lambda *_args: {})
    monkeypatch.setattr(
        "grocery_extract.user_stores_db.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("grocery_extract.ingest.image_needs_store_label", lambda *_args: False)
    monkeypatch.setattr("grocery_extract.ingest.list_products_for_matching", lambda _user_id: [])

    results = accept_upload_batch(uploads, user_id=user_id, max_workers=1, enqueue=False)

    assert len(results) == 3
    image_ids = [result["image_id"] for result in results]
    assert len(set(image_ids)) == 3
    assert all(result["extraction_status"] == "pending" for result in results)

    photos_root = user_dir / "photos"
    for upload_path, image_id in zip(uploads, image_ids, strict=True):
        jpg_path = next(photos_root.glob(f"*/jpg/{image_id}.jpg"))
        assert jpg_path.read_bytes() == upload_path.read_bytes()


def test_bulk_endpoint_passes_distinct_saved_paths(client, monkeypatch):
    reg = client.post(
        "/api/auth/register",
        json={"username": "bulk-uploader", "password": "password123"},
    )
    token = reg.json()["token"]
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")

    captured_bytes: list[bytes] = []

    def fake_batch(paths, **kwargs):
        captured_bytes.extend(path.read_bytes() for path in paths)
        return [
            {
                "image_id": f"IMG_000{i + 1:04d}",
                "products": [],
                "product_count": 0,
                "meta": {},
                "extractor": "cursor_sdk",
                "source": "upload",
            }
            for i in range(len(paths))
        ]

    with patch("server.accept_upload_batch", side_effect=fake_batch):
        resp = client.post(
            "/api/photos/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=[
                ("files", ("image.jpg", b"photo-a", "image/jpeg")),
                ("files", ("image.jpg", b"photo-b", "image/jpeg")),
                ("files", ("image.jpg", b"photo-c", "image/jpeg")),
            ],
            data={"source": "upload"},
        )

    assert resp.status_code == 202, resp.text
    assert len(captured_bytes) == 3
    assert len(set(captured_bytes)) == 3
