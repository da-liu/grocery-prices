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

    original_key, canonical_key, suffix = _persist_image(
        upload,
        image_id,
        date_folder,
        user_id,
    )

    assert suffix == ".webp"
    assert original_key == canonical_key
    assert canonical_key.endswith("/IMG_0001.webp")

    webp_path = tmp_path / "data" / canonical_key
    jpg_path = webp_path.parent / "jpg" / f"{image_id}.jpg"
    assert webp_path.exists()
    assert webp_path.read_bytes() == b"RIFF....WEBP"
    assert not jpg_path.exists()


def test_blob_keys_always_uses_webp_path():
    from grocery_extract.catalog_db import blob_keys

    original, canonical = blob_keys(
        "user-1",
        "2026_07_06",
        "IMG_0002",
        original_suffix=".jpg",
    )
    assert original == "users/user-1/photos/2026_07_06/IMG_0002.webp"
    assert canonical == original


def test_persist_image_rejects_jpeg(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    upload = tmp_path / "upload.jpg"
    upload.write_bytes(b"\xff\xd8\xff")

    with pytest.raises(ValueError, match="Only WebP uploads are supported"):
        _persist_image(upload, "IMG_0003", "2026_07_06", "user-jpeg")
