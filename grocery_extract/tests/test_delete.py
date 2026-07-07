from __future__ import annotations

from pathlib import Path

import uuid

import pytest

from grocery_extract.catalog_db import save_photo_extraction, list_product_rows, save_photo
from grocery_extract.delete import delete_product, delete_products_bulk, prune_orphan_photos


@pytest.fixture
def user_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(
        "grocery_extract.user_stores_db.list_user_stores_as_dicts",
        lambda *_args, **_kwargs: [],
    )

    from extract_server.users_db import init_db, register_user

    init_db()
    user = register_user(f"deleteuser_{uuid.uuid4().hex[:8]}", "password12345")
    user_id = user.id
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)

    try:
        yield user_id, user_dir
    finally:
        from extract_server.scripts.remove_user import remove_registered_user

        remove_registered_user(user_id)


def _write_photo(user_dir: Path, user_id: str, image_id: str) -> str:
    batch_dir = user_dir / "photos" / "2026_06_30"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / f"{image_id}.webp").write_bytes(b"webp")
    return f"users/{user_id}/photos/2026_06_30/{image_id}.webp"


def _seed_products(
    user_id: str,
    user_dir: Path,
    image_id: str,
    products: list[dict],
) -> list[str]:
    key = _write_photo(user_dir, user_id, image_id)
    save_photo(
        user_id,
        photo_id=image_id,
        blob_key=key,
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at="2026-06-30T19:00:00-04:00",
        store_location_id=None,
    )
    save_photo_extraction(
        user_id,
        image_id,
        extractor="cursor_sdk",
        raw_response="[]",
        products=products,
        photo_type="shelf",
    )
    rows = [row for row in list_product_rows(user_id) if row["image_id"] == image_id]
    return [row["id"] for row in rows if not row.get("extraction_empty")]


def test_delete_last_product_removes_photo_files(user_env):
    user_id, user_dir = user_env
    sighting_ids = _seed_products(
        user_id,
        user_dir,
        "IMG_0001",
        [{"product_name": "Milk", "price": 1.0, "category": "dairy"}],
    )

    assert delete_product(user_id, sighting_ids[0])

    assert not (user_dir / "photos" / "2026_06_30" / "IMG_0001.webp").exists()


def test_bulk_delete_last_products_removes_photo_files(user_env):
    user_id, user_dir = user_env
    sighting_ids = _seed_products(
        user_id,
        user_dir,
        "IMG_0001",
        [
            {"product_name": "Milk", "price": 1.0, "category": "dairy"},
            {"product_name": "Bread", "price": 2.0, "category": "bakery"},
        ],
    )

    result = delete_products_bulk(user_id, sighting_ids)

    assert result == {"deleted": 2, "photos_removed": 1, "failed": []}
    assert not (user_dir / "photos" / "2026_06_30" / "IMG_0001.webp").exists()


def test_prune_orphan_photos_removes_photos_without_db_rows(user_env):
    user_id, user_dir = user_env
    _write_photo(user_dir, user_id, "IMG_0009")

    removed = prune_orphan_photos(user_id)

    assert removed == 1
    assert not (user_dir / "photos" / "2026_06_30" / "IMG_0009.webp").exists()
