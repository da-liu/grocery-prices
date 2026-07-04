from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass

from extract_server.users_db import DB_PATH
from grocery_extract.stores import store_from_gps

_LEGACY_USER_STORE_COLUMNS = frozenset({"address", "area", "created_at"})


@dataclass(frozen=True)
class UserStoreLocation:
    id: str
    name: str
    latitude: float
    longitude: float
    match_radius_m: int
    maps_url: str | None
    anchors: list[dict[str, float]] | None = None


@dataclass(frozen=True)
class CreateStoreResult:
    store: UserStoreLocation
    matched_existing: bool


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_user_store_locations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_store_locations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            match_radius_m INTEGER NOT NULL DEFAULT 150,
            maps_url TEXT,
            anchors TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_store_locations_user ON user_store_locations(user_id)"
    )


def _migrate_user_store_locations(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(user_store_locations)").fetchall()
    if not rows:
        return
    colnames = {row[1] for row in rows}
    if not (_LEGACY_USER_STORE_COLUMNS & colnames):
        return

    conn.execute(
        """
        CREATE TABLE user_store_locations_new (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            match_radius_m INTEGER NOT NULL DEFAULT 150,
            maps_url TEXT,
            anchors TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO user_store_locations_new (
            id, user_id, name, latitude, longitude, match_radius_m, maps_url, anchors
        )
        SELECT id, user_id, name, latitude, longitude, match_radius_m, maps_url, NULL
        FROM user_store_locations
        """
    )
    conn.execute("DROP TABLE user_store_locations")
    conn.execute("ALTER TABLE user_store_locations_new RENAME TO user_store_locations")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_store_locations_user ON user_store_locations(user_id)"
    )


def init_user_store_tables() -> None:
    with _connect() as conn:
        _create_user_store_locations_table(conn)
        _migrate_user_store_locations(conn)
        _ensure_anchors_column(conn)


def _ensure_anchors_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(user_store_locations)").fetchall()
    colnames = {row[1] for row in rows}
    if "anchors" not in colnames:
        conn.execute("ALTER TABLE user_store_locations ADD COLUMN anchors TEXT")


def _parse_anchors(raw: str | None) -> list[dict[str, float]] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    anchors: list[dict[str, float]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        lat = item.get("latitude")
        lon = item.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            anchors.append({"latitude": float(lat), "longitude": float(lon)})
    return anchors or None


def _row_to_store(row) -> UserStoreLocation:
    return UserStoreLocation(
        id=row["id"],
        name=row["name"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        match_radius_m=row["match_radius_m"],
        maps_url=row["maps_url"],
        anchors=_parse_anchors(row["anchors"] if "anchors" in row.keys() else None),
    )


def store_as_match_dict(store: UserStoreLocation) -> dict:
    payload = {
        "id": store.id,
        "store": store.name,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "match_radius_m": store.match_radius_m,
        "maps_url": store.maps_url,
    }
    if store.anchors:
        payload["anchors"] = store.anchors
    return payload


def list_user_stores(user_id: str) -> list[UserStoreLocation]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, latitude, longitude, match_radius_m, maps_url, anchors
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
            SELECT id, name, latitude, longitude, match_radius_m, maps_url, anchors
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
) -> CreateStoreResult:
    name = name.strip()
    if not name:
        raise ValueError("Store name is required")

    existing_stores = list_user_stores_as_dicts(user_id)
    matched = store_from_gps(latitude, longitude, existing_stores)
    if matched:
        store = get_user_store(user_id, matched["id"])
        if store is not None:
            return CreateStoreResult(store=store, matched_existing=True)

    store_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_store_locations (
                id, user_id, name, latitude, longitude, match_radius_m, maps_url, anchors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                user_id,
                name,
                latitude,
                longitude,
                match_radius_m,
                maps_url,
                None,
            ),
        )
    store = get_user_store(user_id, store_id)
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


def count_photos_for_store(user_id: str, store_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM photos
            WHERE user_id = ? AND store_location_id = ?
            """,
            (user_id, store_id),
        ).fetchone()
    return int(row["count"]) if row else 0


def merge_user_stores(user_id: str, source_id: str, target_id: str) -> UserStoreLocation | None:
    if source_id == target_id:
        raise ValueError("Cannot merge a store into itself")

    source = get_user_store(user_id, source_id)
    target = get_user_store(user_id, target_id)
    if source is None or target is None:
        return None

    anchors = list(target.anchors or [])
    anchors.append({"latitude": source.latitude, "longitude": source.longitude})
    if target.anchors is None:
        anchors.append({"latitude": target.latitude, "longitude": target.longitude})
    # dedupe anchors by rounded coords
    seen: set[tuple[float, float]] = set()
    unique_anchors: list[dict[str, float]] = []
    for anchor in anchors:
        key = (round(anchor["latitude"], 6), round(anchor["longitude"], 6))
        if key in seen:
            continue
        seen.add(key)
        unique_anchors.append(anchor)

    with _connect() as conn:
        conn.execute(
            """
            UPDATE photos
            SET store_location_id = ?, updated_at = datetime('now')
            WHERE user_id = ? AND store_location_id = ?
            """,
            (target_id, user_id, source_id),
        )
        conn.execute(
            """
            UPDATE user_store_locations
            SET anchors = ?
            WHERE user_id = ? AND id = ?
            """,
            (json.dumps(unique_anchors), user_id, target_id),
        )
        conn.execute(
            "DELETE FROM user_store_locations WHERE user_id = ? AND id = ?",
            (user_id, source_id),
        )
    return get_user_store(user_id, target_id)


def store_to_api_dict(store: UserStoreLocation, *, photo_count: int | None = None) -> dict:
    payload = {
        "id": store.id,
        "name": store.name,
        "latitude": store.latitude,
        "longitude": store.longitude,
        "match_radius_m": store.match_radius_m,
        "maps_url": store.maps_url,
        "anchors": store.anchors,
    }
    if photo_count is not None:
        payload["photo_count"] = photo_count
    return payload
