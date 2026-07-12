from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from extract_server.db import list_product_rows, save_photo, save_photo_extraction
from extract_server.db.connection import get_conn


@pytest.fixture
def user_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(
        "extract_server.db.user_stores.list_user_stores_as_dicts",
        lambda *_args, **_kwargs: [],
    )

    from extract_server.db import init_db, register_user

    init_db()
    user = register_user(f"listuser_{uuid.uuid4().hex[:8]}", "password12345")
    user_id = user.id
    user_dir = tmp_path / "data" / "users" / user_id
    user_dir.mkdir(parents=True)
    yield user_id, user_dir


def _seed_photo(
    user_id: str,
    user_dir: Path,
    image_id: str,
    *,
    captured_at: str | None,
    product_name: str,
) -> None:
    batch_dir = user_dir / "photos" / "2026_07_11"
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / f"{image_id}.webp").write_bytes(b"webp")
    key = f"users/{user_id}/photos/2026_07_11/{image_id}.webp"
    save_photo(
        user_id,
        photo_id=image_id,
        blob_key=key,
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at=captured_at,
        store_location_id=None,
    )
    save_photo_extraction(
        user_id,
        image_id,
        extractor="gemini_direct",
        raw_response="[]",
        products=[{"product_name": product_name, "price": 1.0, "category": "dairy"}],
        photo_type="shelf",
    )


def test_list_product_rows_includes_created_at_and_coalesce_order(user_env):
    user_id, user_dir = user_env
    _seed_photo(
        user_id,
        user_dir,
        "IMG_OLD",
        captured_at="2026-01-01T12:00:00Z",
        product_name="Old Milk",
    )
    _seed_photo(
        user_id,
        user_dir,
        "IMG_NEW",
        captured_at=None,
        product_name="New Milk",
    )

    conn = get_conn()
    conn.execute(
        """
        UPDATE photos
        SET created_at = ?
        WHERE user_id = ? AND id = ?
        """,
        ("2026-07-11T18:00:00+00:00", user_id, "IMG_NEW"),
    )
    conn.commit()

    rows = list_product_rows(user_id)
    by_image = {row["image_id"]: row for row in rows}

    assert "created_at" in by_image["IMG_NEW"]
    assert by_image["IMG_NEW"]["created_at"]
    assert by_image["IMG_NEW"]["captured_at"] is None
    assert by_image["IMG_OLD"]["captured_at"] == "2026-01-01T12:00:00Z"

    image_order = [row["image_id"] for row in rows]
    assert image_order.index("IMG_NEW") < image_order.index("IMG_OLD")
