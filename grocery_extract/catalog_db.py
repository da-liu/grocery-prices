from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from extract_server.users_db import get_conn
from grocery_extract.product_matching import attach_price_insights, build_price_insights, overlapping_product_keys
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.schema import ExtractedProduct, fold_product_fields
from grocery_extract.stores import store_from_gps
from grocery_extract.user_paths import find_user_jpg, resolve_blob_path

TORONTO = ZoneInfo("America/Toronto")
EMPTY_SIGHTING_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
PHOTO_ID_RE = re.compile(r"^(?:[a-f0-9]{32}|IMG_\d+)$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _toronto_now() -> str:
    return datetime.now(TORONTO).isoformat(timespec="seconds")


def init_catalog_tables() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('shelf', 'receipt')),
            blob_key TEXT NOT NULL,
            content_hash TEXT,
            gps_latitude REAL,
            gps_longitude REAL,
            captured_at TEXT,
            store_location_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (store_location_id) REFERENCES user_store_locations(id)
                ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_content_hash
            ON photos(user_id, content_hash)
            WHERE content_hash IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_photos_user_captured
            ON photos(user_id, captured_at DESC);

        CREATE INDEX IF NOT EXISTS idx_photos_user_store
            ON photos(user_id, store_location_id);

        CREATE TABLE IF NOT EXISTS extractions (
            user_id TEXT NOT NULL,
            photo_id TEXT NOT NULL,
            extractor TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            reextracted_at TEXT,
            manually_edited_at TEXT,
            raw_response TEXT,
            llm_ms INTEGER,
            other_ms INTEGER,
            model TEXT,
            product_count INTEGER,
            photo_type TEXT,
            extraction_error TEXT,
            PRIMARY KEY (user_id, photo_id),
            FOREIGN KEY (user_id, photo_id) REFERENCES photos(user_id, id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS product_sightings (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            photo_id TEXT NOT NULL,
            line_index INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price REAL,
            other TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id, photo_id) REFERENCES photos(user_id, id) ON DELETE CASCADE,
            UNIQUE (user_id, photo_id, line_index),
            CHECK (json_valid(other))
        );

        CREATE INDEX IF NOT EXISTS idx_sightings_user_photo
            ON product_sightings(user_id, photo_id);
        """
    )


def extraction_timing_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("llm_ms") is None and row.get("other_ms") is None:
        return None
    payload = {
        "llm_ms": row.get("llm_ms"),
        "other_ms": row.get("other_ms"),
        "model": row.get("model"),
    }
    return {key: value for key, value in payload.items() if value is not None}


def blob_key(user_id: str, date_folder: str, image_id: str) -> str:
    return f"users/{user_id}/photos/{date_folder}/{image_id}.webp"


def is_valid_photo_id(photo_id: str) -> bool:
    return bool(PHOTO_ID_RE.match(photo_id))


def new_photo_id() -> str:
    return uuid.uuid4().hex


def new_photo_ids(count: int) -> list[str]:
    if count <= 0:
        return []
    return [new_photo_id() for _ in range(count)]


def empty_sighting_id(user_id: str, photo_id: str) -> str:
    return uuid.uuid5(EMPTY_SIGHTING_NS, f"{user_id}/{photo_id}/empty").hex


def photo_type_from_ingest_source(source: str) -> str:
    return "receipt" if source == "receipt" else "shelf"


def _normalize_other(product: dict[str, Any]) -> dict[str, Any]:
    folded = fold_product_fields(product)
    other = dict(folded.get("other") or {})
    for key in ("unit", "unit_price", "category"):
        if key in folded:
            if folded[key] is None:
                other.pop(key, None)
            else:
                other[key] = folded[key]
    if other.get("is_special") is False:
        other.pop("is_special", None)
    return other


def _split_product_fields(
    product: dict[str, Any],
) -> tuple[str, float | None, dict[str, Any]]:
    product_name = str(product["product_name"])
    price = product.get("price")
    return product_name, price, _normalize_other(product)


def _merge_sighting_row(row: Any) -> dict[str, Any]:
    other = dict(json.loads(row["other"] or "{}"))
    return {
        "product_name": row["product_name"],
        "price": row["price"],
        **other,
        "other": other,
    }


def find_photo_by_content_hash(user_id: str, content_hash: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id FROM photos
        WHERE user_id = ? AND content_hash = ?
        """,
        (user_id, content_hash),
    ).fetchone()
    return row["id"] if row else None


def _extraction_status(extraction: dict[str, Any] | None) -> str:
    if extraction is None:
        return "pending"
    if extraction.get("extraction_error"):
        return "failed"
    return "done"


def get_photo(user_id: str, photo_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, user_id, type, blob_key, content_hash,
               gps_latitude, gps_longitude, captured_at, store_location_id,
               created_at, updated_at
        FROM photos
        WHERE user_id = ? AND id = ?
        """,
        (user_id, photo_id),
    ).fetchone()
    return dict(row) if row else None


def get_photo_blob_path(user_id: str, photo_id: str) -> Path | None:
    photo = get_photo(user_id, photo_id)
    if photo is None:
        return None
    path = resolve_blob_path(photo["blob_key"])
    return path if path.exists() else None


def set_photo_store_location_id(
    user_id: str,
    photo_id: str,
    store_location_id: str | None,
) -> bool:
    now = _utc_now()
    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE photos
        SET store_location_id = ?, updated_at = ?
        WHERE user_id = ? AND id = ?
        """,
        (store_location_id, now, user_id, photo_id),
    )
    return cur.rowcount > 0


def get_photo_store_location_id(user_id: str, photo_id: str) -> str | None:
    photo = get_photo(user_id, photo_id)
    if photo is None:
        return None
    value = photo.get("store_location_id")
    return value if isinstance(value, str) and value else None


def count_extractions(user_id: str) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM extractions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["count"]) if row else 0


def _location_for_photo(
    photo: dict[str, Any],
    *,
    user_stores: list[dict],
    user_store_by_id: dict[str, dict],
) -> dict[str, Any]:
    assigned = photo.get("store_location_id")
    lat = photo.get("gps_latitude")
    lon = photo.get("gps_longitude")

    if assigned and assigned in user_store_by_id:
        store = user_store_by_id[assigned]
        location = {
            "store": store.get("store") or store.get("name") or "Unknown store",
            "store_location_id": assigned,
        }
    elif lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            location = {
                "store": matched.get("store") or matched.get("name") or "Unknown store",
                "store_location_id": matched.get("id"),
            }
        else:
            location = {"store": "Unknown store"}
    else:
        location = {"store": "Unknown store"}

    if lat is not None and lon is not None:
        location["latitude"] = lat
        location["longitude"] = lon
    return location


def save_photo(
    user_id: str,
    *,
    photo_id: str,
    photo_type: str,
    blob_key: str,
    content_hash: str | None,
    gps_latitude: float | None,
    gps_longitude: float | None,
    captured_at: str | None,
    store_location_id: str | None,
) -> None:
    now = _utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        """
        INSERT INTO photos (
            id, user_id, type, blob_key, content_hash,
            gps_latitude, gps_longitude, captured_at, store_location_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            photo_id,
            user_id,
            photo_type,
            blob_key,
            content_hash,
            gps_latitude,
            gps_longitude,
            captured_at,
            store_location_id,
            now,
            now,
        ),
    )
    conn.commit()


def record_photo_extraction_failure(user_id: str, photo_id: str, error: str) -> None:
    now = _toronto_now()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO extractions (
            user_id, photo_id, extractor, extracted_at, extraction_error, product_count
        ) VALUES (?, ?, '_failed', ?, ?, 0)
        ON CONFLICT(user_id, photo_id) DO UPDATE SET
            extractor = excluded.extractor,
            extracted_at = excluded.extracted_at,
            extraction_error = excluded.extraction_error,
            product_count = 0
        """,
        (user_id, photo_id, now, error),
    )


def _set_photo_type(
    conn: sqlite3.Connection,
    user_id: str,
    photo_id: str,
    photo_type: str,
) -> None:
    now = _utc_now()
    if photo_type == "receipt":
        conn.execute(
            """
            UPDATE photos
            SET type = ?, store_location_id = NULL, updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (photo_type, now, user_id, photo_id),
        )
    else:
        conn.execute(
            """
            UPDATE photos
            SET type = ?, updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (photo_type, now, user_id, photo_id),
        )


def _insert_extraction_row(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    photo_id: str,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    llm_ms: int | None,
    other_ms: int | None,
    model: str | None,
    photo_type: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO extractions (
            user_id, photo_id, extractor, extracted_at, raw_response,
            llm_ms, other_ms, model, product_count, photo_type, extraction_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            user_id,
            photo_id,
            extractor,
            _toronto_now(),
            raw_response,
            llm_ms,
            other_ms,
            model,
            len(products),
            photo_type,
        ),
    )


def _update_extraction_row(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    photo_id: str,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    reextracted: bool,
    llm_ms: int | None,
    other_ms: int | None,
    model: str | None,
    photo_type: str | None,
) -> None:
    extracted_at = _toronto_now()
    timing_sets = (
        ", llm_ms = ?, other_ms = ?, model = ?, product_count = ?, "
        "photo_type = ?, extraction_error = NULL"
    )
    timing_values = (
        llm_ms,
        other_ms,
        model,
        len(products),
        photo_type,
    )
    if reextracted:
        conn.execute(
            f"""
            UPDATE extractions
            SET extractor = ?, extracted_at = ?, reextracted_at = ?, raw_response = ?{timing_sets}
            WHERE user_id = ? AND photo_id = ?
            """,
            (extractor, extracted_at, extracted_at, raw_response, *timing_values, user_id, photo_id),
        )
    else:
        conn.execute(
            f"""
            UPDATE extractions
            SET extractor = ?, extracted_at = ?, raw_response = ?{timing_sets}
            WHERE user_id = ? AND photo_id = ?
            """,
            (extractor, extracted_at, raw_response, *timing_values, user_id, photo_id),
        )


def _insert_product_sightings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    photo_id: str,
    products: list[dict[str, Any]],
    now: str,
) -> None:
    for index, product in enumerate(products, start=1):
        product_name, price, other = _split_product_fields(product)
        conn.execute(
            """
            INSERT INTO product_sightings (
                id, user_id, photo_id, line_index, product_name, price, other,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                user_id,
                photo_id,
                index,
                product_name,
                price,
                json.dumps(other, ensure_ascii=False),
                now,
                now,
            ),
        )


def finalize_photo_extraction(
    user_id: str,
    photo_id: str,
    *,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    llm_ms: int | None = None,
    other_ms: int | None = None,
    model: str | None = None,
    photo_type: str | None = None,
) -> int:
    now = _utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    _insert_extraction_row(
        conn,
        user_id=user_id,
        photo_id=photo_id,
        extractor=extractor,
        raw_response=raw_response,
        products=products,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        photo_type=photo_type,
    )
    _insert_product_sightings(conn, user_id=user_id, photo_id=photo_id, products=products, now=now)
    if photo_type:
        _set_photo_type(conn, user_id, photo_id, photo_type)
    conn.commit()
    return len(products)


def save_photo_ingest(
    user_id: str,
    *,
    photo_id: str,
    photo_type: str,
    blob_key: str,
    content_hash: str | None,
    gps_latitude: float | None,
    gps_longitude: float | None,
    captured_at: str | None,
    store_location_id: str | None,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    llm_ms: int | None = None,
    other_ms: int | None = None,
    model: str | None = None,
) -> int:
    now = _utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        """
        INSERT INTO photos (
            id, user_id, type, blob_key, content_hash,
            gps_latitude, gps_longitude, captured_at, store_location_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            photo_id,
            user_id,
            photo_type,
            blob_key,
            content_hash,
            gps_latitude,
            gps_longitude,
            captured_at,
            store_location_id,
            now,
            now,
        ),
    )
    _insert_extraction_row(
        conn,
        user_id=user_id,
        photo_id=photo_id,
        extractor=extractor,
        raw_response=raw_response,
        products=products,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        photo_type=photo_type,
    )
    _insert_product_sightings(conn, user_id=user_id, photo_id=photo_id, products=products, now=now)
    conn.commit()
    return len(products)


def replace_photo_extraction(
    user_id: str,
    photo_id: str,
    *,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    reextracted: bool = False,
    llm_ms: int | None = None,
    other_ms: int | None = None,
    model: str | None = None,
    photo_type: str | None = None,
) -> int:
    now = _utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    _update_extraction_row(
        conn,
        user_id=user_id,
        photo_id=photo_id,
        extractor=extractor,
        raw_response=raw_response,
        products=products,
        reextracted=reextracted,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        photo_type=photo_type,
    )
    conn.execute(
        "DELETE FROM product_sightings WHERE user_id = ? AND photo_id = ?",
        (user_id, photo_id),
    )
    _insert_product_sightings(conn, user_id=user_id, photo_id=photo_id, products=products, now=now)
    if photo_type:
        _set_photo_type(conn, user_id, photo_id, photo_type)
    conn.commit()
    return len(products)


def get_extraction(user_id: str, photo_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT user_id, photo_id, extractor, extracted_at, reextracted_at,
               manually_edited_at, raw_response, llm_ms, other_ms, model,
               product_count, photo_type, extraction_error
        FROM extractions
        WHERE user_id = ? AND photo_id = ?
        """,
        (user_id, photo_id),
    ).fetchone()
    return dict(row) if row else None


def get_sighting(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, user_id, photo_id, line_index, product_name, price, other,
               created_at, updated_at
        FROM product_sightings
        WHERE user_id = ? AND id = ?
        """,
        (user_id, sighting_id),
    ).fetchone()
    return dict(row) if row else None


def update_sighting(user_id: str, sighting_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    row = get_sighting(user_id, sighting_id)
    if row is None:
        return None

    merged = _merge_sighting_row(row)
    for key, value in updates.items():
        if key == "other" and isinstance(value, dict):
            merged_other = dict(merged.get("other") or {})
            for other_key, other_value in value.items():
                if other_value is None:
                    merged_other.pop(other_key, None)
                    merged.pop(other_key, None)
                else:
                    merged_other[other_key] = other_value
                    merged[other_key] = other_value
            merged["other"] = merged_other
        elif value is None and key in {"price", "unit_price"}:
            merged[key] = None
        elif value is None and key not in {"product_name", "other"}:
            merged[key] = None
        elif value is not None:
            merged[key] = value

    product_name, price, other = _split_product_fields(merged)
    now = _utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        """
        UPDATE product_sightings
        SET product_name = ?, price = ?, other = ?, updated_at = ?
        WHERE user_id = ? AND id = ?
        """,
        (
            product_name,
            price,
            json.dumps(other, ensure_ascii=False),
            now,
            user_id,
            sighting_id,
        ),
    )
    conn.execute(
        """
        UPDATE extractions
        SET manually_edited_at = ?
        WHERE user_id = ? AND photo_id = ?
        """,
        (_toronto_now(), user_id, row["photo_id"]),
    )
    conn.commit()
    return build_product_row(user_id, sighting_id)


def add_sighting(user_id: str, photo_id: str, product: dict[str, Any]) -> dict[str, Any] | None:
    product_name, price, other = _split_product_fields(product)
    now = _utc_now()
    sighting_id = uuid.uuid4().hex
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    photo_exists = conn.execute(
        "SELECT 1 FROM photos WHERE user_id = ? AND id = ?",
        (user_id, photo_id),
    ).fetchone()
    if photo_exists is None:
        conn.rollback()
        return None

    extraction_exists = conn.execute(
        "SELECT 1 FROM extractions WHERE user_id = ? AND photo_id = ?",
        (user_id, photo_id),
    ).fetchone()
    if extraction_exists is None:
        conn.execute(
            """
            INSERT INTO extractions (
                user_id, photo_id, extractor, extracted_at, raw_response
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, photo_id, "manual", _toronto_now(), None),
        )
    row = conn.execute(
        """
        SELECT COALESCE(MAX(line_index), 0) AS max_index
        FROM product_sightings
        WHERE user_id = ? AND photo_id = ?
        """,
        (user_id, photo_id),
    ).fetchone()
    line_index = int(row["max_index"]) + 1
    conn.execute(
        """
        INSERT INTO product_sightings (
            id, user_id, photo_id, line_index, product_name, price, other,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sighting_id,
            user_id,
            photo_id,
            line_index,
            product_name,
            price,
            json.dumps(other, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    return build_product_row(user_id, sighting_id)


def delete_photo(user_id: str, photo_id: str) -> bool:
    photo = get_photo(user_id, photo_id)
    if photo is None:
        return False

    _delete_photo_files(photo)
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM photos WHERE user_id = ? AND id = ?",
        (user_id, photo_id),
    )
    return cur.rowcount > 0


def _delete_photo_files(photo: dict[str, Any]) -> None:
    blob_key = photo.get("blob_key")
    if not blob_key:
        return
    resolve_blob_path(blob_key).unlink(missing_ok=True)


def photo_id_for_empty_sighting(user_id: str, product_id: str) -> str | None:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.id
        FROM photos p
        LEFT JOIN product_sightings s
            ON s.user_id = p.user_id AND s.photo_id = p.id
        WHERE p.user_id = ? AND s.id IS NULL
        """,
        (user_id,),
    ).fetchall()
    for row in rows:
        if empty_sighting_id(user_id, row["id"]) == product_id:
            return row["id"]
    return None


def delete_sighting(user_id: str, sighting_id: str) -> bool:
    empty_photo_id = photo_id_for_empty_sighting(user_id, sighting_id)
    if empty_photo_id is not None:
        return delete_photo(user_id, empty_photo_id)

    row = get_sighting(user_id, sighting_id)
    if row is None:
        return False

    photo_id = row["photo_id"]
    conn = get_conn()
    conn.execute(
        "DELETE FROM product_sightings WHERE user_id = ? AND id = ?",
        (user_id, sighting_id),
    )
    remaining = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM product_sightings
        WHERE user_id = ? AND photo_id = ?
        """,
        (user_id, photo_id),
    ).fetchone()

    if int(remaining["count"]) == 0:
        return delete_photo(user_id, photo_id)
    return True


def delete_sightings_bulk(user_id: str, sighting_ids: list[str]) -> dict[str, Any]:
    deleted = 0
    photos_removed = 0
    failed: list[str] = []
    seen: set[str] = set()
    touched_photos: set[str] = set()

    for sighting_id in sighting_ids:
        if sighting_id in seen:
            continue
        seen.add(sighting_id)

        empty_photo_id = photo_id_for_empty_sighting(user_id, sighting_id)
        if empty_photo_id is not None:
            if delete_photo(user_id, empty_photo_id):
                deleted += 1
                photos_removed += 1
            else:
                failed.append(sighting_id)
            continue

        row = get_sighting(user_id, sighting_id)
        if row is None:
            failed.append(sighting_id)
            continue

        conn = get_conn()
        conn.execute(
            "DELETE FROM product_sightings WHERE user_id = ? AND id = ?",
            (user_id, sighting_id),
        )
        deleted += 1
        touched_photos.add(row["photo_id"])

    for photo_id in touched_photos:
        conn = get_conn()
        remaining = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM product_sightings
            WHERE user_id = ? AND photo_id = ?
            """,
            (user_id, photo_id),
        ).fetchone()
        if int(remaining["count"]) == 0 and delete_photo(user_id, photo_id):
            photos_removed += 1

    prune_orphan_photo_files(user_id)
    return {"deleted": deleted, "photos_removed": photos_removed, "failed": failed}


def prune_orphan_photo_files(user_id: str) -> int:
    from grocery_extract.user_paths import DATA_DIR, user_root

    db_ids = set()
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, blob_key FROM photos WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    db_ids = {row["id"] for row in rows}
    db_blob_keys = {row["blob_key"] for row in rows}

    photos_root = user_root(user_id) / "photos"
    if not photos_root.exists():
        return 0

    removed = 0
    for path in photos_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".webp" or path.parent.name == "jpg":
            continue
        image_id = path.stem
        rel = path.relative_to(DATA_DIR).as_posix()
        if image_id not in db_ids and rel not in db_blob_keys:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def list_product_rows(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    db = conn or get_conn()
    user_stores = list_user_stores_as_dicts(user_id, conn=db)
    user_store_by_id = {store["id"]: store for store in user_stores}

    photos = db.execute(
        """
        SELECT p.id, p.type, p.gps_latitude, p.gps_longitude,
               p.captured_at, p.store_location_id
        FROM photos p
        INNER JOIN extractions e ON e.user_id = p.user_id AND e.photo_id = p.id
        WHERE p.user_id = ? AND e.extraction_error IS NULL
        ORDER BY p.captured_at DESC, p.id DESC
        """,
        (user_id,),
    ).fetchall()
    sightings = db.execute(
        """
        SELECT id, photo_id, line_index, product_name, price, other
        FROM product_sightings
        WHERE user_id = ?
        ORDER BY photo_id, line_index
        """,
        (user_id,),
    ).fetchall()

    sightings_by_photo: dict[str, list[Any]] = {}
    for row in sightings:
        sightings_by_photo.setdefault(row["photo_id"], []).append(row)

    lines: list[dict[str, Any]] = []
    for photo in photos:
        photo_dict = dict(photo)
        location = _location_for_photo(
            photo_dict,
            user_stores=user_stores,
            user_store_by_id=user_store_by_id,
        )
        image_path = f"api/media/{photo_dict['id']}"
        captured_at = photo_dict.get("captured_at")

        photo_sightings = sightings_by_photo.get(photo_dict["id"], [])
        if not photo_sightings:
            lines.append(
                {
                    "id": empty_sighting_id(user_id, photo_dict["id"]),
                    "image_id": photo_dict["id"],
                    "image_path": image_path,
                    "price_currency": "CAD",
                    "captured_at": captured_at,
                    "location": location,
                    "photo_type": photo_dict.get("type") or "shelf",
                    "product_name": "No products extracted",
                    "category": "pantry",
                    "price": None,
                    "extraction_empty": True,
                }
            )
            continue

        for row in photo_sightings:
            merged = _merge_sighting_row(row)
            lines.append(
                {
                    "id": row["id"],
                    "image_id": photo_dict["id"],
                    "image_path": image_path,
                    "price_currency": "CAD",
                    "captured_at": captured_at,
                    "location": location,
                    "photo_type": photo_dict.get("type") or "shelf",
                    **merged,
                }
            )

    return attach_price_insights(lines)


def list_products_for_matching(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
    user_stores: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    db = conn or get_conn()
    stores = user_stores if user_stores is not None else list_user_stores_as_dicts(user_id, conn=db)
    user_store_by_id = {store["id"]: store for store in stores}

    photos = db.execute(
        """
        SELECT p.id, p.gps_latitude, p.gps_longitude, p.captured_at, p.store_location_id
        FROM photos p
        INNER JOIN extractions e ON e.user_id = p.user_id AND e.photo_id = p.id
        WHERE p.user_id = ? AND e.extraction_error IS NULL
        """,
        (user_id,),
    ).fetchall()
    sightings = db.execute(
        """
        SELECT id, photo_id, product_name, price, other
        FROM product_sightings
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()

    sightings_by_photo: dict[str, list[Any]] = {}
    for row in sightings:
        sightings_by_photo.setdefault(row["photo_id"], []).append(row)

    lines: list[dict[str, Any]] = []
    for photo in photos:
        photo_dict = dict(photo)
        location = _location_for_photo(
            photo_dict,
            user_stores=stores,
            user_store_by_id=user_store_by_id,
        )
        captured_at = photo_dict.get("captured_at")
        for row in sightings_by_photo.get(photo_dict["id"], []):
            merged = _merge_sighting_row(row)
            lines.append(
                {
                    "id": row["id"],
                    "image_id": photo_dict["id"],
                    "captured_at": captured_at,
                    "location": location,
                    **merged,
                }
            )
    return lines


def get_photos_extraction_status(
    user_id: str,
    image_ids: list[str],
    *,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    if not image_ids:
        return []

    placeholders = ",".join("?" for _ in image_ids)
    db = conn or get_conn()
    photos = db.execute(
        f"""
        SELECT id, gps_latitude, gps_longitude, captured_at, store_location_id, type
        FROM photos
        WHERE user_id = ? AND id IN ({placeholders})
        """,
        (user_id, *image_ids),
    ).fetchall()
    sightings = db.execute(
        f"""
        SELECT photo_id, product_name, price, other, line_index
        FROM product_sightings
        WHERE user_id = ? AND photo_id IN ({placeholders})
        ORDER BY photo_id, line_index
        """,
        (user_id, *image_ids),
    ).fetchall()
    extractions = db.execute(
        f"""
        SELECT photo_id, llm_ms, other_ms, model, extraction_error
        FROM extractions
        WHERE user_id = ? AND photo_id IN ({placeholders})
        """,
        (user_id, *image_ids),
    ).fetchall()

    extraction_by_photo = {row["photo_id"]: dict(row) for row in extractions}
    sightings_by_photo: dict[str, list[dict[str, Any]]] = {}
    for row in sightings:
        merged = _merge_sighting_row(row)
        sightings_by_photo.setdefault(row["photo_id"], []).append(merged)

    photo_by_id = {row["id"]: dict(row) for row in photos}
    results: list[dict[str, Any]] = []
    for image_id in image_ids:
        photo = photo_by_id.get(image_id)
        if photo is None:
            continue
        extraction = extraction_by_photo.get(image_id)
        status = _extraction_status(extraction)
        products = sightings_by_photo.get(image_id, [])
        product_count = len(products)
        payload: dict[str, Any] = {
            "image_id": image_id,
            "image_path": f"api/media/{image_id}",
            "extraction_status": status,
            "photo_type": photo.get("type") or "shelf",
            "detected_receipt": photo.get("type") == "receipt",
            "product_count": product_count,
            "products": products,
            "extraction_empty": status == "done" and product_count == 0,
            "meta": {
                "gps_latitude": photo.get("gps_latitude"),
                "gps_longitude": photo.get("gps_longitude"),
                "captured_at": photo.get("captured_at"),
                "store_location_id": photo.get("store_location_id"),
            },
        }
        store_location_id = photo.get("store_location_id")
        if isinstance(store_location_id, str) and store_location_id:
            payload["store_location_id"] = store_location_id
        if extraction and extraction.get("extraction_error"):
            payload["extraction_error"] = extraction["extraction_error"]
        timing = extraction_timing_payload(extraction or {})
        if timing:
            payload["extraction_timing"] = timing
        results.append(payload)
    return results


def _product_line_for_sighting(
    user_id: str,
    sighting_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    db = conn or get_conn()
    sighting = db.execute(
        """
        SELECT id, photo_id, line_index, product_name, price, other
        FROM product_sightings
        WHERE user_id = ? AND id = ?
        """,
        (user_id, sighting_id),
    ).fetchone()
    if sighting is None:
        return None

    photo = db.execute(
        """
        SELECT p.id, p.type, p.gps_latitude, p.gps_longitude, p.captured_at, p.store_location_id
        FROM photos p
        INNER JOIN extractions e ON e.user_id = p.user_id AND e.photo_id = p.id
        WHERE p.user_id = ? AND p.id = ? AND e.extraction_error IS NULL
        """,
        (user_id, sighting["photo_id"]),
    ).fetchone()
    if photo is None:
        return None

    user_stores = list_user_stores_as_dicts(user_id, conn=db)
    user_store_by_id = {store["id"]: store for store in user_stores}
    photo_dict = dict(photo)
    location = _location_for_photo(
        photo_dict,
        user_stores=user_stores,
        user_store_by_id=user_store_by_id,
    )
    merged = _merge_sighting_row(sighting)
    return {
        "id": sighting["id"],
        "image_id": photo_dict["id"],
        "image_path": f"api/media/{photo_dict['id']}",
        "price_currency": "CAD",
        "captured_at": photo_dict.get("captured_at"),
        "location": location,
        "photo_type": photo_dict.get("type") or "shelf",
        **merged,
    }


def build_product_row(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    line = _product_line_for_sighting(user_id, sighting_id)
    if line is None:
        return None
    insights = build_price_insights(line, list_products_for_matching(user_id))
    if insights:
        line["price_insights"] = insights
    return line


def count_sightings_for_user(user_id: str) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM product_sightings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["count"]) if row else 0


EDITABLE_FIELDS = {
    "product_name",
    "other",
    "price",
    "unit",
    "unit_price",
    "category",
}


def update_product(user_id: str, product_id: str, updates: dict) -> dict | None:
    filtered = {key: value for key, value in updates.items() if key in EDITABLE_FIELDS}
    if not filtered:
        return None
    return update_sighting(user_id, product_id, filtered)


def add_product(user_id: str, image_id: str, product: dict) -> dict | None:
    if not is_valid_photo_id(image_id):
        return None
    if get_photo(user_id, image_id) is None:
        return None

    cleaned = {key: value for key, value in product.items() if key in EDITABLE_FIELDS and value is not None}
    if not cleaned.get("product_name"):
        return None
    if not cleaned.get("category"):
        cleaned["category"] = "pantry"

    try:
        ExtractedProduct.model_validate(cleaned)
    except Exception:
        return None

    return add_sighting(user_id, image_id, cleaned)


def reextract_photo(
    user_id: str,
    image_id: str,
    *,
    api_key: str | None = None,
    extract_backend: str | None = None,
) -> dict | None:
    if not is_valid_photo_id(image_id):
        return None

    jpg_path = find_user_jpg(user_id, image_id)
    if jpg_path is None or not jpg_path.exists():
        return None

    photo = get_photo(user_id, image_id)
    extraction = get_extraction(user_id, image_id)
    if photo is None or extraction is None:
        return None

    result = extract_from_upload(
        jpg_path,
        image_id=image_id,
        api_key=api_key,
        backend=extract_backend,
        skip_normalize=True,
    )

    products = [product.to_product_dict() for product in result.products]
    timing = result.timing
    product_count = replace_photo_extraction(
        user_id,
        image_id,
        extractor=result.extractor,
        raw_response=result.raw_response,
        products=products,
        reextracted=True,
        llm_ms=timing.llm_ms if timing else None,
        other_ms=timing.other_ms if timing else None,
        model=timing.model if timing else None,
        photo_type=result.photo_type,
    )

    all_products = list_products_for_matching(user_id)
    new_rows = [row for row in all_products if row["image_id"] == image_id]
    existing_rows = [row for row in all_products if row["image_id"] != image_id]
    overlaps = overlapping_product_keys(new_rows, existing_rows)

    updated = get_extraction(user_id, image_id)
    timing = extraction_timing_payload(updated) if updated else None

    return {
        "image_id": image_id,
        "products": products,
        "product_count": product_count,
        "overlapping_products": overlaps,
        "extraction_empty": len(products) == 0,
        **({"extraction_timing": timing} if timing else {}),
    }
