from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from extract_server.db._helpers import one
from extract_server.db.connection import get_conn
from extract_server.extraction.stores import maps_url_for_coords, store_from_gps


@dataclass(frozen=True)
class UserStoreLocation:
    id: str
    name: str
    latitude: float
    longitude: float
    match_radius_m: int


@dataclass(frozen=True)
class CreateStoreResult:
    store: UserStoreLocation
    matched_existing: bool


def init_user_store_tables() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_store_locations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            match_radius_m INTEGER NOT NULL DEFAULT 150
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_store_locations_user ON user_store_locations(user_id)"
    )


def _row_to_store(row) -> UserStoreLocation:
    return UserStoreLocation(
        id=row["id"],
        name=row["name"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        match_radius_m=row["match_radius_m"],
    )


def store_as_match_dict(store: UserStoreLocation) -> dict:
    return {
        "id": store.id,
        "store": store.name,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "match_radius_m": store.match_radius_m,
        "maps_url": maps_url_for_coords(store.latitude, store.longitude),
    }


def list_user_stores(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[UserStoreLocation]:
    db = conn or get_conn()
    rows = db.execute(
        """
        SELECT id, name, latitude, longitude, match_radius_m
        FROM user_store_locations
        WHERE user_id = ?
        ORDER BY name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    return [_row_to_store(row) for row in rows]


def list_user_stores_as_dicts(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    return [store_as_match_dict(store) for store in list_user_stores(user_id, conn=conn)]


def get_user_store(
    user_id: str,
    store_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> UserStoreLocation | None:
    db = conn or get_conn()
    row = db.execute(
        """
        SELECT id, name, latitude, longitude, match_radius_m
        FROM user_store_locations
        WHERE user_id = ? AND id = ?
        """,
        (user_id, store_id),
    ).fetchone()
    return _row_to_store(row) if row else None


def create_user_store(
    user_id: str,
    *,
    name: str,
    latitude: float,
    longitude: float,
    match_radius_m: int = 150,
) -> CreateStoreResult:
    name = name.strip()
    if not name:
        raise ValueError("Store name is required")

    conn = get_conn()
    existing_stores = list_user_stores_as_dicts(user_id, conn=conn)
    matched = store_from_gps(latitude, longitude, existing_stores)
    if matched:
        store = get_user_store(user_id, matched["id"], conn=conn)
        if store is not None:
            return CreateStoreResult(store=store, matched_existing=True)

    store_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO user_store_locations (
            id, user_id, name, latitude, longitude, match_radius_m
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (store_id, user_id, name, latitude, longitude, match_radius_m),
    )
    store = get_user_store(user_id, store_id, conn=conn)
    assert store is not None
    return CreateStoreResult(store=store, matched_existing=False)


def update_user_store(
    user_id: str,
    store_id: str,
    *,
    name: str,
    latitude: float,
    longitude: float,
    match_radius_m: int = 150,
) -> UserStoreLocation | None:
    name = name.strip()
    if not name:
        raise ValueError("Store name is required")

    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE user_store_locations
        SET name = ?, latitude = ?, longitude = ?,
            match_radius_m = ?
        WHERE user_id = ? AND id = ?
        """,
        (name, latitude, longitude, match_radius_m, user_id, store_id),
    )
    if cur.rowcount == 0:
        return None
    return get_user_store(user_id, store_id, conn=conn)


def delete_user_store(user_id: str, store_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM user_store_locations WHERE user_id = ? AND id = ?",
        (user_id, store_id),
    )
    return cur.rowcount > 0


def count_photos_for_store(
    user_id: str,
    store_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    db = conn or get_conn()
    row = db.execute(
        """
        SELECT COUNT(*) AS count
        FROM photos
        WHERE user_id = ? AND store_location_id = ?
        """,
        (user_id, store_id),
    ).fetchone()
    return int(row["count"]) if row else 0


def store_to_api_dict(store: UserStoreLocation, *, photo_count: int | None = None) -> dict:
    payload = {
        "id": store.id,
        "name": store.name,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "match_radius_m": store.match_radius_m,
        "maps_url": maps_url_for_coords(store.latitude, store.longitude),
    }
    if photo_count is not None:
        payload["photo_count"] = photo_count
    return payload
