from __future__ import annotations

from pathlib import Path

import pytest

from grocery_extract.catalog_db import init_catalog_tables
from grocery_extract.ingest import _persist_image


def test_persist_image_keeps_webp_without_jpeg_copy(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    init_catalog_tables()
    user_id = "user-webp"
    date_folder = "2026_07_06"
    image_id = "IMG_0001"
    upload = tmp_path / "upload.webp"
    upload.write_bytes(b"RIFF....WEBP")

    key = _persist_image(
        upload,
        image_id,
        date_folder,
        user_id,
    )

    assert key.endswith("/IMG_0001.webp")

    webp_path = tmp_path / "data" / key
    jpg_path = webp_path.parent / "jpg" / f"{image_id}.jpg"
    assert webp_path.exists()
    assert webp_path.read_bytes() == b"RIFF....WEBP"
    assert not jpg_path.exists()


def test_blob_key_uses_webp_path():
    from grocery_extract.catalog_db import blob_key

    key = blob_key("user-1", "2026_07_06", "IMG_0002")
    assert key == "users/user-1/photos/2026_07_06/IMG_0002.webp"


def test_blob_key_uses_jpg_path():
    from grocery_extract.catalog_db import blob_key

    assert blob_key("user-1", "2026_07_06", "IMG_0003", ".jpg") == (
        "users/user-1/photos/2026_07_06/IMG_0003.jpg"
    )
    assert blob_key("user-1", "2026_07_06", "IMG_0004", ".jpeg") == (
        "users/user-1/photos/2026_07_06/IMG_0004.jpg"
    )


@pytest.mark.parametrize("upload_name", ["upload.jpg", "upload.jpeg"])
def test_persist_image_accepts_jpeg(tmp_path: Path, monkeypatch, upload_name: str):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    init_catalog_tables()
    user_id = "user-jpeg"
    date_folder = "2026_07_06"
    image_id = "IMG_0003"
    upload = tmp_path / upload_name
    upload.write_bytes(b"\xff\xd8\xff jpeg-bytes")

    key = _persist_image(upload, image_id, date_folder, user_id)

    assert key.endswith("/IMG_0003.jpg")
    jpg_path = tmp_path / "data" / key
    assert jpg_path.exists()
    assert jpg_path.read_bytes() == b"\xff\xd8\xff jpeg-bytes"


def test_persist_image_rejects_unsupported_types(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    upload = tmp_path / "upload.png"
    upload.write_bytes(b"\x89PNG")

    with pytest.raises(ValueError, match="Unsupported image type"):
        _persist_image(upload, "IMG_0005", "2026_07_06", "user-png")
