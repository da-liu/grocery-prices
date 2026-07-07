from __future__ import annotations

from pathlib import Path

from grocery_extract.duplicate import file_content_hash, find_exact_duplicate


def test_file_content_hash(tmp_path: Path):
    path = tmp_path / "sample.jpg"
    path.write_bytes(b"same-bytes")
    assert file_content_hash(path) == file_content_hash(path)


def test_find_exact_duplicate(tmp_path: Path, monkeypatch):
    user_id = "user-1"
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user
    from grocery_extract.catalog_db import save_photo_extraction, save_photo

    init_db()
    user = register_user("dupuser", "password12345")
    user_id = user.id
    batch_dir = tmp_path / "data" / "users" / user_id / "photos" / "2026_07_02"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "IMG_0001.webp").write_bytes(b"webp")
    save_photo(
        user_id,
        photo_id="IMG_0001",
        blob_key=f"users/{user_id}/photos/2026_07_02/IMG_0001.webp",
        content_hash="abc123",
        gps_latitude=None,
        gps_longitude=None,
        captured_at=None,
        store_location_id=None,
    )
    save_photo_extraction(
        user_id,
        "IMG_0001",
        extractor="cursor_sdk",
        raw_response=None,
        products=[],
        photo_type="shelf",
    )

    assert find_exact_duplicate(user_id, "abc123") == "IMG_0001"
    assert find_exact_duplicate(user_id, "missing") is None
