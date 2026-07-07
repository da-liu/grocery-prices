from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from extract_server.db._helpers import one, utc_now
from extract_server.db.connection import get_conn
from extract_server.grocery_extract import user_paths


def init_photos_table() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            type TEXT CHECK (type IS NULL OR type IN ('shelf', 'receipt')),
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
        """
    )


def find_photo_by_content_hash(user_id: str, content_hash: str) -> str | None:
    conn = get_conn()
    row = one(
        conn,
        "SELECT id FROM photos WHERE user_id = ? AND content_hash = ?",
        (user_id, content_hash),
    )
    return row["id"] if row else None


def get_photo(user_id: str, photo_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    return one(
        conn,
        """
        SELECT id, user_id, type, blob_key, content_hash,
               gps_latitude, gps_longitude, captured_at, store_location_id,
               created_at, updated_at
        FROM photos
        WHERE user_id = ? AND id = ?
        """,
        (user_id, photo_id),
    )


def get_photo_blob_path(user_id: str, photo_id: str) -> Path | None:
    photo = get_photo(user_id, photo_id)
    if photo is None:
        return None
    path = user_paths.resolve_blob_path(photo["blob_key"])
    return path if path.exists() else None


def set_photo_store_location_id(
    user_id: str,
    photo_id: str,
    store_location_id: str | None,
) -> bool:
    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE photos
        SET store_location_id = ?, updated_at = ?
        WHERE user_id = ? AND id = ?
        """,
        (store_location_id, utc_now(), user_id, photo_id),
    )
    return cur.rowcount > 0


def get_photo_store_location_id(user_id: str, photo_id: str) -> str | None:
    conn = get_conn()
    row = one(
        conn,
        "SELECT store_location_id FROM photos WHERE user_id = ? AND id = ?",
        (user_id, photo_id),
    )
    if row is None:
        return None
    value = row["store_location_id"]
    return value if isinstance(value, str) and value else None


def save_photo(
    user_id: str,
    *,
    photo_id: str,
    blob_key: str,
    content_hash: str | None,
    gps_latitude: float | None,
    gps_longitude: float | None,
    captured_at: str | None,
    store_location_id: str | None,
) -> None:
    now = utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        """
        INSERT INTO photos (
            id, user_id, type, blob_key, content_hash,
            gps_latitude, gps_longitude, captured_at, store_location_id,
            created_at, updated_at
        ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            photo_id,
            user_id,
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


def _delete_photo_files(photo: dict[str, Any]) -> None:
    blob = photo.get("blob_key")
    if blob:
        user_paths.resolve_blob_path(blob).unlink(missing_ok=True)


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


def set_photo_type(
    conn: sqlite3.Connection,
    user_id: str,
    photo_id: str,
    photo_type: str,
) -> None:
    now = utc_now()
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


def prune_orphan_photo_files(user_id: str) -> int:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, blob_key FROM photos WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    db_ids = {row["id"] for row in rows}
    db_blob_keys = {row["blob_key"] for row in rows}

    photos_root = user_paths.user_root(user_id) / "photos"
    if not photos_root.exists():
        return 0

    removed = 0
    for path in photos_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".webp" or path.parent.name == "jpg":
            continue
        image_id = path.stem
        rel = path.relative_to(user_paths.data_dir()).as_posix()
        if image_id not in db_ids and rel not in db_blob_keys:
            path.unlink(missing_ok=True)
            removed += 1
    return removed
