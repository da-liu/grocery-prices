from __future__ import annotations

import json
from pathlib import Path

import pytest

from grocery_extract.duplicate import file_content_hash, find_exact_duplicate
from grocery_extract.product_matching import (
    attach_price_insights,
    build_price_insights,
    overlapping_product_keys,
    product_match_key,
)


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
    from grocery_extract.catalog_db import save_photo_ingest

    init_db()
    user = register_user("dupuser", "password12345")
    user_id = user.id
    save_photo_ingest(
        user_id,
        photo_id="IMG_0001",
        photo_type="shelf",
        original_blob_key=None,
        jpeg_blob_key=f"users/{user_id}/photos/2026_07_02/jpg/IMG_0001.jpg",
        content_hash="abc123",
        gps_latitude=None,
        gps_longitude=None,
        captured_at=None,
        store_location_id=None,
        extractor="cursor_sdk",
        raw_response=None,
        products=[],
    )

    assert find_exact_duplicate(user_id, "abc123") == "IMG_0001"
    assert find_exact_duplicate(user_id, "missing") is None


def test_product_match_key_prefers_barcode():
    assert product_match_key({"barcode": "0123", "product_name": "Milk"}) == "barcode:0123"
    assert product_match_key({"product_name": "Milk"}) == "name:milk"


def test_build_price_insights_same_store():
    products = [
        {
            "id": "IMG_0001-1",
            "image_id": "IMG_0001",
            "product_name": "Milk",
            "price": 5.99,
            "captured_at": "2026-07-01T10:00:00",
            "location": {"store": "Store A"},
        },
        {
            "id": "IMG_0002-1",
            "image_id": "IMG_0002",
            "product_name": "Milk",
            "price": 6.49,
            "captured_at": "2026-07-02T10:00:00",
            "location": {"store": "Store A"},
        },
    ]
    insights = build_price_insights(products[1], products)
    assert len(insights) == 1
    assert insights[0]["insight_type"] == "same_store_history"
    assert insights[0]["price"] == 5.99


def test_overlapping_product_keys():
    existing = [
        {
            "id": "IMG_0001-1",
            "product_name": "Bread",
            "barcode": "111",
            "price": 3.49,
            "location": {"store": "Store A"},
            "captured_at": "2026-06-01",
        }
    ]
    new_rows = [{"product_name": "Bread", "barcode": "111", "price": 3.99}]
    overlaps = overlapping_product_keys(new_rows, existing)
    assert len(overlaps) == 1
    assert overlaps[0]["existing_product_id"] == "IMG_0001-1"


def test_attach_price_insights():
    products = [
        {
            "id": "IMG_0001-1",
            "product_name": "Eggs",
            "price": 4.99,
            "location": {"store": "Store A"},
            "captured_at": "2026-07-01",
        },
        {
            "id": "IMG_0002-1",
            "product_name": "Eggs",
            "price": 5.49,
            "location": {"store": "Store B"},
            "captured_at": "2026-07-02",
        },
    ]
    enriched = attach_price_insights(products)
    assert enriched[1].get("price_insights")
    assert enriched[1]["price_insights"][0]["store"] == "Store A"
