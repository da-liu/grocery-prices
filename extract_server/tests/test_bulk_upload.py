from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from grocery_extract.ingest import allocate_image_ids, ingest_upload_batch, next_image_id


def test_allocate_image_ids_returns_unique_sequential_ids(tmp_path: Path, monkeypatch):
    user_id = "user-bulk"
    photos_root = tmp_path / "data" / "users" / user_id / "photos" / "2026_07_02" / "jpg"
    photos_root.mkdir(parents=True)
    (photos_root / "IMG_0003.jpg").write_bytes(b"x")

    monkeypatch.setattr("grocery_extract.ingest.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.ingest.user_root", lambda uid: tmp_path / "data" / "users" / uid)
    monkeypatch.setattr(
        "grocery_extract.ingest.user_extractions_dir",
        lambda uid: tmp_path / "data" / "users" / uid / "extractions",
    )

    ids = allocate_image_ids(user_id, 3)
    assert ids == ["IMG_0004", "IMG_0005", "IMG_0006"]
    assert next_image_id(user_id) == "IMG_0004"


def test_ingest_upload_batch_assigns_distinct_image_ids(tmp_path: Path, monkeypatch):
    user_id = "user-batch"
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)

    uploads = []
    for index in range(3):
        path = tmp_path / f"image-{index}.jpg"
        path.write_bytes(f"photo-{index}".encode())
        uploads.append(path)

    seen_image_ids: list[str] = []

    def fake_extract(upload_path: Path, **kwargs):
        from grocery_extract.schema import ExtractionResult, ImageMeta

        image_id = kwargs["image_id"]
        seen_image_ids.append(image_id)
        return ExtractionResult(
            image_path=str(upload_path),
            meta=ImageMeta(image_id=image_id, source_file=str(upload_path)),
            products=[],
            raw_response="[]",
            extractor="cursor_sdk",
        )

    monkeypatch.setattr("grocery_extract.ingest.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.ingest.user_root", lambda uid: tmp_path / "data" / "users" / uid)
    monkeypatch.setattr(
        "grocery_extract.ingest.user_extractions_dir",
        lambda uid: tmp_path / "data" / "users" / uid / "extractions",
    )
    monkeypatch.setattr("grocery_extract.ingest.user_meta_path", lambda uid: user_dir / ".meta.json")
    monkeypatch.setattr(
        "grocery_extract.ingest.user_photos_dir",
        lambda uid, date_folder: user_dir / "photos" / date_folder,
    )
    monkeypatch.setattr("grocery_extract.ingest.extract_from_upload", fake_extract)
    monkeypatch.setattr("grocery_extract.ingest.file_content_hash", lambda path: path.read_bytes().decode())
    monkeypatch.setattr("grocery_extract.ingest.find_exact_duplicate", lambda *_args: None)
    monkeypatch.setattr("grocery_extract.ingest.extract_exif", lambda *_args: {})
    monkeypatch.setattr(
        "grocery_extract.user_stores_db.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("grocery_extract.ingest.auto_assign_store_from_gps", lambda *_args: None)
    monkeypatch.setattr("grocery_extract.photo_stores.image_needs_store_label", lambda *_args: False)
    monkeypatch.setattr("grocery_extract.ingest.build_product_lines", lambda **_kwargs: [])
    monkeypatch.setattr("grocery_extract.ingest.write_user_products_jsonl", lambda *_args: 0)

    results = ingest_upload_batch(uploads, user_id=user_id, max_workers=1)

    assert len(results) == 3
    image_ids = [result["image_id"] for result in results]
    assert len(set(image_ids)) == 3
    assert set(seen_image_ids) == set(image_ids)

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

    with patch("server.ingest_upload_batch", side_effect=fake_batch):
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

    assert resp.status_code == 200, resp.text
    assert len(captured_bytes) == 3
    assert len(set(captured_bytes)) == 3
