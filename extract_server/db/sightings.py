from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from extract_server.db._helpers import count as db_count
from extract_server.db._helpers import one, utc_now
from extract_server.db._ids import empty_sighting_id
from extract_server.db._product_fields import merge_sighting_row, split_product_fields
from extract_server.db.connection import get_conn
from extract_server.db.photos import delete_photo


def init_sightings_table() -> None:
    conn = get_conn()
    conn.executescript(
        """
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


def get_sighting(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    return one(
        conn,
        """
        SELECT id, user_id, photo_id, line_index, product_name, price, other,
               created_at, updated_at
        FROM product_sightings
        WHERE user_id = ? AND id = ?
        """,
        (user_id, sighting_id),
    )


def insert_sighting_row(
    conn: sqlite3.Connection,
    *,
    sighting_id: str,
    user_id: str,
    photo_id: str,
    line_index: int,
    product: dict[str, Any],
    now: str,
) -> None:
    product_name, price, other = split_product_fields(product)
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


def insert_sightings(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    photo_id: str,
    products: list[dict[str, Any]],
    now: str,
) -> None:
    for index, product in enumerate(products, start=1):
        insert_sighting_row(
            conn,
            sighting_id=uuid.uuid4().hex,
            user_id=user_id,
            photo_id=photo_id,
            line_index=index,
            product=product,
            now=now,
        )


def delete_sightings_for_photo(
    conn: sqlite3.Connection,
    user_id: str,
    photo_id: str,
) -> None:
    conn.execute(
        "DELETE FROM product_sightings WHERE user_id = ? AND photo_id = ?",
        (user_id, photo_id),
    )


def _next_line_index(conn: sqlite3.Connection, user_id: str, photo_id: str) -> int:
    row = one(
        conn,
        """
        SELECT COALESCE(MAX(line_index), 0) AS max_index
        FROM product_sightings
        WHERE user_id = ? AND photo_id = ?
        """,
        (user_id, photo_id),
    )
    return int(row["max_index"]) + 1 if row else 1


def update_sighting(user_id: str, sighting_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    row = get_sighting(user_id, sighting_id)
    if row is None:
        return None

    merged = merge_sighting_row(row)
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

    product_name, price, other = split_product_fields(merged)
    now = utc_now()
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
    from extract_server.db.extractions import mark_manually_edited
    from extract_server.db.queries import build_product_row

    mark_manually_edited(conn, user_id, row["photo_id"])
    conn.commit()
    return build_product_row(user_id, sighting_id)


def add_sighting(user_id: str, photo_id: str, product: dict[str, Any]) -> dict[str, Any] | None:
    now = utc_now()
    sighting_id = uuid.uuid4().hex
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    if one(conn, "SELECT 1 AS ok FROM photos WHERE user_id = ? AND id = ?", (user_id, photo_id)) is None:
        conn.rollback()
        return None

    from extract_server.db.extractions import ensure_manual_extraction
    from extract_server.db.queries import build_product_row

    ensure_manual_extraction(conn, user_id, photo_id)
    line_index = _next_line_index(conn, user_id, photo_id)
    insert_sighting_row(
        conn,
        sighting_id=sighting_id,
        user_id=user_id,
        photo_id=photo_id,
        line_index=line_index,
        product=product,
        now=now,
    )
    conn.commit()
    return build_product_row(user_id, sighting_id)


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


def _delete_sighting_row(conn: sqlite3.Connection, user_id: str, sighting_id: str) -> str | None:
    row = one(
        conn,
        "SELECT photo_id FROM product_sightings WHERE user_id = ? AND id = ?",
        (user_id, sighting_id),
    )
    if row is None:
        return None
    conn.execute(
        "DELETE FROM product_sightings WHERE user_id = ? AND id = ?",
        (user_id, sighting_id),
    )
    return row["photo_id"]


def _maybe_delete_empty_photo(user_id: str, photo_id: str) -> bool:
    conn = get_conn()
    remaining = db_count(
        conn,
        "SELECT COUNT(*) AS count FROM product_sightings WHERE user_id = ? AND photo_id = ?",
        (user_id, photo_id),
    )
    if remaining == 0:
        return delete_photo(user_id, photo_id)
    return True


def delete_sighting(user_id: str, sighting_id: str) -> bool:
    empty_photo_id = photo_id_for_empty_sighting(user_id, sighting_id)
    if empty_photo_id is not None:
        return delete_photo(user_id, empty_photo_id)

    conn = get_conn()
    photo_id = _delete_sighting_row(conn, user_id, sighting_id)
    if photo_id is None:
        return False
    return _maybe_delete_empty_photo(user_id, photo_id)


def delete_sightings_bulk(user_id: str, sighting_ids: list[str]) -> dict[str, Any]:
    from extract_server.db.photos import prune_orphan_photo_files

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

        conn = get_conn()
        photo_id = _delete_sighting_row(conn, user_id, sighting_id)
        if photo_id is None:
            failed.append(sighting_id)
            continue

        deleted += 1
        touched_photos.add(photo_id)

    for photo_id in touched_photos:
        conn = get_conn()
        remaining = db_count(
            conn,
            "SELECT COUNT(*) AS count FROM product_sightings WHERE user_id = ? AND photo_id = ?",
            (user_id, photo_id),
        )
        if remaining == 0 and delete_photo(user_id, photo_id):
            photos_removed += 1

    prune_orphan_photo_files(user_id)
    return {"deleted": deleted, "photos_removed": photos_removed, "failed": failed}


def count_sightings_for_user(user_id: str) -> int:
    conn = get_conn()
    return db_count(
        conn,
        "SELECT COUNT(*) AS count FROM product_sightings WHERE user_id = ?",
        (user_id,),
    )
