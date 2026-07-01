from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "extract_server" / "data" / "grocery.db"


@dataclass(frozen=True)
class UserStoreLocation:
    id: str
    name: str
    latitude: float
    longitude: float
    match_radius_m: int
    maps_url: str | None


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_user_store_tables() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_store_locations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                address TEXT,
                area TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                match_radius_m INTEGER NOT NULL DEFAULT 150,
                maps_url TEXT,
                created_at TEXT NOT NULL
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
        maps_url=row["maps_url"],
    )


def store_as_match_dict(store: UserStoreLocation) -> dict:
    return {
        "id": store.id,
        "store": store.name,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "match_radius_m": store.match_radius_m,
        "maps_url": store.maps_url,
    }


def list_user_stores(user_id: str) -> list[UserStoreLocation]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, latitude, longitude, match_radius_m, maps_url
            FROM user_store_locations
            WHERE user_id = ?
            ORDER BY name COLLATE NOCASE
            """,
            (user_id,),
        ).fetchall()
    return [_row_to_store(row) for row in rows]


def list_user_stores_as_dicts(user_id: str) -> list[dict]:
    return [store_as_match_dict(store) for store in list_user_stores(user_id)]


def get_user_store(user_id: str, store_id: str) -> UserStoreLocation | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, latitude, longitude, match_radius_m, maps_url
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
    maps_url: str | None = None,
) -> UserStoreLocation:
    name = name.strip()
    if not name:
        raise ValueError("Store name is required")

    store_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_store_locations (
                id, user_id, name, address, area, latitude, longitude,
                match_radius_m, maps_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                user_id,
                name,
                None,
                None,
                latitude,
                longitude,
                match_radius_m,
                maps_url,
                created_at,
            ),
        )
    store = get_user_store(user_id, store_id)
    assert store is not None
    return store


def update_user_store(
    user_id: str,
    store_id: str,
    *,
    name: str,
    latitude: float,
    longitude: float,
    match_radius_m: int = 150,
    maps_url: str | None = None,
) -> UserStoreLocation | None:
    name = name.strip()
    if not name:
        raise ValueError("Store name is required")

    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE user_store_locations
            SET name = ?, latitude = ?, longitude = ?,
                match_radius_m = ?, maps_url = ?
            WHERE user_id = ? AND id = ?
            """,
            (
                name,
                latitude,
                longitude,
                match_radius_m,
                maps_url,
                user_id,
                store_id,
            ),
        )
    if cur.rowcount == 0:
        return None
    return get_user_store(user_id, store_id)


def delete_user_store(user_id: str, store_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM user_store_locations WHERE user_id = ? AND id = ?",
            (user_id, store_id),
        )
    return cur.rowcount > 0


def store_to_api_dict(store: UserStoreLocation) -> dict:
    return {
        "id": store.id,
        "name": store.name,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "match_radius_m": store.match_radius_m,
        "maps_url": store.maps_url,
    }
