from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from grocery_extract.ingest import accept_upload


def test_accept_upload_uses_client_exif_when_provided(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user

    init_db()
    user = register_user("exifuser", "password12345")
    user_id = user.id
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)

    upload = tmp_path / "photo.jpg"
    upload.write_bytes(b"compressed-bytes-without-exif")

    monkeypatch.setattr(
        "grocery_extract.ingest.user_photos_dir",
        lambda uid, date_folder: user_dir / "photos" / date_folder,
    )
    monkeypatch.setattr("grocery_extract.ingest.file_content_hash", lambda _path: "hash123")
    monkeypatch.setattr("grocery_extract.ingest.find_photo_by_content_hash", lambda *_args: None)
    monkeypatch.setattr(
        "grocery_extract.ingest.extract_exif",
        lambda _path: (_ for _ in ()).throw(AssertionError("should not read file exif")),
    )
    monkeypatch.setattr(
        "grocery_extract.user_stores_db.list_user_stores_as_dicts",
        lambda *_args: [],
    )
    monkeypatch.setattr("grocery_extract.ingest.image_needs_store_label", lambda *_args: False)
    monkeypatch.setattr("grocery_extract.ingest.list_products_for_matching", lambda _user_id: [])

    with patch("grocery_extract.ingest.classify_photo_type") as classify:
        classify.return_value.photo_type = "shelf"
        classify.return_value.classify_ms = 1
        result = accept_upload(
            upload,
            user_id=user_id,
            source="upload",
            client_exif={
                "GPSLatitude": 43.6532,
                "GPSLongitude": -79.3832,
                "DateTimeOriginal": "2026:07:04 18:30:00",
            },
        )

    assert result["meta"]["gps_latitude"] == 43.6532
    assert result["meta"]["gps_longitude"] == -79.3832
    assert result["meta"]["captured_at"] == "2026-07-04T18:30:00"
    assert result["date_folder"] == "2026_07_04"
