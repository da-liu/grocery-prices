from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from extract_server.users_db import _connect
from grocery_extract.exif import captured_at_from_exif
from grocery_extract.product_matching import attach_price_insights
from grocery_extract.stores import store_from_gps
from grocery_extract.user_paths import resolve_blob_path

TORONTO = ZoneInfo("America/Toronto")
EMPTY_SIGHTING_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

SIGHTING_COLUMNS = frozenset({"product_name", "brand", "price"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _toronto_now() -> str:
    return datetime.now(TORONTO).isoformat(timespec="seconds")


def init_catalog_tables() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_image_seq (
                user_id TEXT PRIMARY KEY,
                next_num INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photos (
                id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('shelf', 'receipt')),
                original_blob_key TEXT,
                jpeg_blob_key TEXT NOT NULL,
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
                PRIMARY KEY (user_id, photo_id),
                FOREIGN KEY (user_id, photo_id) REFERENCES photos(user_id, id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS product_sightings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                photo_id TEXT NOT NULL,
                line_index INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                brand TEXT,
                price REAL,
                extras TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id, photo_id) REFERENCES photos(user_id, id) ON DELETE CASCADE,
                UNIQUE (user_id, photo_id, line_index),
                CHECK (json_valid(extras))
            );

            CREATE INDEX IF NOT EXISTS idx_sightings_user_photo
                ON product_sightings(user_id, photo_id);
            """
        )
        photo_columns = {row[1] for row in conn.execute("PRAGMA table_info(photos)")}
        if "extraction_status" not in photo_columns:
            conn.execute(
                "ALTER TABLE photos ADD COLUMN extraction_status TEXT NOT NULL DEFAULT 'done'"
            )
        if "extraction_error" not in photo_columns:
            conn.execute("ALTER TABLE photos ADD COLUMN extraction_error TEXT")


def blob_keys(
    user_id: str,
    date_folder: str,
    image_id: str,
    *,
    original_suffix: str,
) -> tuple[str, str]:
    base = f"users/{user_id}/photos/{date_folder}"
    original = f"{base}/{image_id}{original_suffix}"
    jpeg = f"{base}/jpg/{image_id}.jpg"
    return original, jpeg


def empty_sighting_id(user_id: str, photo_id: str) -> str:
    return uuid.uuid5(EMPTY_SIGHTING_NS, f"{user_id}/{photo_id}/empty").hex


def photo_type_from_ingest_source(source: str) -> str:
    return "receipt" if source == "receipt" else "shelf"


def _split_product_fields(product: dict[str, Any]) -> tuple[str, str | None, float | None, dict[str, Any]]:
    product_name = str(product["product_name"])
    brand = product.get("brand")
    price = product.get("price")
    extras = {
        key: value
        for key, value in product.items()
        if key not in SIGHTING_COLUMNS and value is not None
    }
    if product.get("is_special") is False:
        extras.pop("is_special", None)
    return product_name, brand, price, extras


def _merge_sighting_row(row: Any) -> dict[str, Any]:
    extras = json.loads(row["extras"] or "{}")
    return {
        "product_name": row["product_name"],
        "brand": row["brand"],
        "price": row["price"],
        **extras,
    }


def _photo_num(photo_id: str) -> int | None:
    if not photo_id.startswith("IMG_") or not photo_id[4:].isdigit():
        return None
    return int(photo_id[4:])


def _bump_image_seq(conn, user_id: str, photo_id: str) -> None:
    num = _photo_num(photo_id)
    if num is None:
        return
    next_num = num + 1
    row = conn.execute(
        "SELECT next_num FROM user_image_seq WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO user_image_seq (user_id, next_num) VALUES (?, ?)",
            (user_id, next_num),
        )
    elif next_num > row["next_num"]:
        conn.execute(
            "UPDATE user_image_seq SET next_num = ? WHERE user_id = ?",
            (next_num, user_id),
        )


def allocate_image_ids(user_id: str, count: int) -> list[str]:
    if count <= 0:
        return []
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT next_num FROM user_image_seq WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            start = 1
            conn.execute(
                "INSERT INTO user_image_seq (user_id, next_num) VALUES (?, ?)",
                (user_id, start + count),
            )
        else:
            start = row["next_num"]
            conn.execute(
                "UPDATE user_image_seq SET next_num = ? WHERE user_id = ?",
                (start + count, user_id),
            )
        conn.commit()
    return [f"IMG_{start + index:04d}" for index in range(count)]


def next_image_id(user_id: str) -> str:
    return allocate_image_ids(user_id, 1)[0]


def max_image_num(user_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT next_num FROM user_image_seq WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return 0
    return row["next_num"] - 1


def find_photo_by_content_hash(user_id: str, content_hash: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM photos
            WHERE user_id = ? AND content_hash = ?
            """,
            (user_id, content_hash),
        ).fetchone()
    return row["id"] if row else None


def get_photo(user_id: str, photo_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, type, original_blob_key, jpeg_blob_key, content_hash,
                   gps_latitude, gps_longitude, captured_at, store_location_id,
                   created_at, updated_at, extraction_status, extraction_error
            FROM photos
            WHERE user_id = ? AND id = ?
            """,
            (user_id, photo_id),
        ).fetchone()
    return dict(row) if row else None


def get_photo_jpeg_path(user_id: str, photo_id: str) -> Path | None:
    photo = get_photo(user_id, photo_id)
    if photo is None:
        return None
    path = resolve_blob_path(photo["jpeg_blob_key"])
    return path if path.exists() else None


def set_photo_store_location_id(
    user_id: str,
    photo_id: str,
    store_location_id: str | None,
) -> bool:
    now = _utc_now()
    with _connect() as conn:
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
    with _connect() as conn:
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
        if maps_url := store.get("maps_url"):
            location["maps_url"] = maps_url
    elif lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            location = {
                "store": matched.get("store") or matched.get("name") or "Unknown store",
                "store_location_id": matched.get("id"),
            }
            if maps_url := matched.get("maps_url"):
                location["maps_url"] = maps_url
        else:
            location = {"store": "Unknown store"}
    else:
        location = {"store": "Unknown store"}

    if lat is not None and lon is not None:
        location["latitude"] = lat
        location["longitude"] = lon
    return location


def save_photo_pending(
    user_id: str,
    *,
    photo_id: str,
    photo_type: str,
    original_blob_key: str | None,
    jpeg_blob_key: str,
    content_hash: str | None,
    gps_latitude: float | None,
    gps_longitude: float | None,
    captured_at: str | None,
    store_location_id: str | None,
) -> None:
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO photos (
                id, user_id, type, original_blob_key, jpeg_blob_key, content_hash,
                gps_latitude, gps_longitude, captured_at, store_location_id,
                created_at, updated_at, extraction_status, extraction_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL)
            """,
            (
                photo_id,
                user_id,
                photo_type,
                original_blob_key,
                jpeg_blob_key,
                content_hash,
                gps_latitude,
                gps_longitude,
                captured_at,
                store_location_id,
                now,
                now,
            ),
        )
        _bump_image_seq(conn, user_id, photo_id)
        conn.commit()


def set_extraction_status(
    user_id: str,
    photo_id: str,
    status: str,
    *,
    error: str | None = None,
) -> None:
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE photos
            SET extraction_status = ?, extraction_error = ?, updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (status, error, now, user_id, photo_id),
        )


def finalize_photo_extraction(
    user_id: str,
    photo_id: str,
    *,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
) -> int:
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO extractions (
                user_id, photo_id, extractor, extracted_at, raw_response
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, photo_id, extractor, _toronto_now(), raw_response),
        )
        for index, product in enumerate(products, start=1):
            product_name, brand, price, extras = _split_product_fields(product)
            conn.execute(
                """
                INSERT INTO product_sightings (
                    id, user_id, photo_id, line_index, product_name, brand, price,
                    extras, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    user_id,
                    photo_id,
                    index,
                    product_name,
                    brand,
                    price,
                    json.dumps(extras, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        conn.execute(
            """
            UPDATE photos
            SET extraction_status = 'done', extraction_error = NULL, updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (now, user_id, photo_id),
        )
        conn.commit()
    return len(products)


def save_photo_ingest(
    user_id: str,
    *,
    photo_id: str,
    photo_type: str,
    original_blob_key: str | None,
    jpeg_blob_key: str,
    content_hash: str | None,
    gps_latitude: float | None,
    gps_longitude: float | None,
    captured_at: str | None,
    store_location_id: str | None,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
) -> int:
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO photos (
                id, user_id, type, original_blob_key, jpeg_blob_key, content_hash,
                gps_latitude, gps_longitude, captured_at, store_location_id,
                created_at, updated_at, extraction_status, extraction_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'done', NULL)
            """,
            (
                photo_id,
                user_id,
                photo_type,
                original_blob_key,
                jpeg_blob_key,
                content_hash,
                gps_latitude,
                gps_longitude,
                captured_at,
                store_location_id,
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO extractions (
                user_id, photo_id, extractor, extracted_at, raw_response
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, photo_id, extractor, _toronto_now(), raw_response),
        )
        for index, product in enumerate(products, start=1):
            product_name, brand, price, extras = _split_product_fields(product)
            conn.execute(
                """
                INSERT INTO product_sightings (
                    id, user_id, photo_id, line_index, product_name, brand, price,
                    extras, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    user_id,
                    photo_id,
                    index,
                    product_name,
                    brand,
                    price,
                    json.dumps(extras, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        _bump_image_seq(conn, user_id, photo_id)
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
) -> int:
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        extracted_at = _toronto_now()
        if reextracted:
            conn.execute(
                """
                UPDATE extractions
                SET extractor = ?, extracted_at = ?, reextracted_at = ?, raw_response = ?
                WHERE user_id = ? AND photo_id = ?
                """,
                (extractor, extracted_at, extracted_at, raw_response, user_id, photo_id),
            )
        else:
            conn.execute(
                """
                UPDATE extractions
                SET extractor = ?, extracted_at = ?, raw_response = ?
                WHERE user_id = ? AND photo_id = ?
                """,
                (extractor, extracted_at, raw_response, user_id, photo_id),
            )
        conn.execute(
            "DELETE FROM product_sightings WHERE user_id = ? AND photo_id = ?",
            (user_id, photo_id),
        )
        for index, product in enumerate(products, start=1):
            product_name, brand, price, extras = _split_product_fields(product)
            conn.execute(
                """
                INSERT INTO product_sightings (
                    id, user_id, photo_id, line_index, product_name, brand, price,
                    extras, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    user_id,
                    photo_id,
                    index,
                    product_name,
                    brand,
                    price,
                    json.dumps(extras, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        conn.commit()
    return len(products)


def get_extraction(user_id: str, photo_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT user_id, photo_id, extractor, extracted_at, reextracted_at,
                   manually_edited_at, raw_response
            FROM extractions
            WHERE user_id = ? AND photo_id = ?
            """,
            (user_id, photo_id),
        ).fetchone()
    return dict(row) if row else None


def get_sighting(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, photo_id, line_index, product_name, brand, price,
                   extras, created_at, updated_at
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
        if value is None and key in {"price", "regular_price", "unit_price", "unit_price_per_100g"}:
            merged[key] = None
        elif value is not None:
            merged[key] = value

    product_name, brand, price, extras = _split_product_fields(merged)
    now = _utc_now()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            UPDATE product_sightings
            SET product_name = ?, brand = ?, price = ?, extras = ?, updated_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (
                product_name,
                brand,
                price,
                json.dumps(extras, ensure_ascii=False),
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
    if get_photo(user_id, photo_id) is None:
        return None

    product_name, brand, price, extras = _split_product_fields(product)
    now = _utc_now()
    sighting_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if get_extraction(user_id, photo_id) is None:
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
                id, user_id, photo_id, line_index, product_name, brand, price,
                extras, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sighting_id,
                user_id,
                photo_id,
                line_index,
                product_name,
                brand,
                price,
                json.dumps(extras, ensure_ascii=False),
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
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM photos WHERE user_id = ? AND id = ?",
            (user_id, photo_id),
        )
    return cur.rowcount > 0


def _delete_photo_files(photo: dict[str, Any]) -> None:
    for key in ("original_blob_key", "jpeg_blob_key"):
        blob_key = photo.get(key)
        if not blob_key:
            continue
        path = resolve_blob_path(blob_key)
        path.unlink(missing_ok=True)


def photo_id_for_empty_sighting(user_id: str, product_id: str) -> str | None:
    with _connect() as conn:
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
    with _connect() as conn:
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

        with _connect() as conn:
            conn.execute(
                "DELETE FROM product_sightings WHERE user_id = ? AND id = ?",
                (user_id, sighting_id),
            )
        deleted += 1
        touched_photos.add(row["photo_id"])

    for photo_id in touched_photos:
        with _connect() as conn:
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
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, jpeg_blob_key FROM photos WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    db_ids = {row["id"] for row in rows}
    db_jpegs = {row["jpeg_blob_key"] for row in rows}

    photos_root = user_root(user_id) / "photos"
    if not photos_root.exists():
        return 0

    removed = 0
    for path in photos_root.rglob("IMG_*.*"):
        if path.suffix.lower() == ".jpg" and path.parent.name == "jpg":
            image_id = path.stem
        elif path.name.startswith("IMG_"):
            image_id = path.stem
        else:
            continue
        rel = path.relative_to(DATA_DIR).as_posix()
        if image_id not in db_ids and rel not in db_jpegs:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def list_product_rows(user_id: str) -> list[dict[str, Any]]:
    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)
    user_store_by_id = {store["id"]: store for store in user_stores}

    with _connect() as conn:
        photos = conn.execute(
            """
            SELECT id, type, jpeg_blob_key, gps_latitude, gps_longitude,
                   captured_at, store_location_id
            FROM photos
            WHERE user_id = ? AND extraction_status = 'done'
            ORDER BY captured_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        sightings = conn.execute(
            """
            SELECT id, photo_id, line_index, product_name, brand, price, extras
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
                    **merged,
                }
            )

    return attach_price_insights(lines)


def list_products_for_matching(user_id: str) -> list[dict[str, Any]]:
    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)
    user_store_by_id = {store["id"]: store for store in user_stores}

    with _connect() as conn:
        photos = conn.execute(
            """
            SELECT id, gps_latitude, gps_longitude, captured_at, store_location_id
            FROM photos
            WHERE user_id = ? AND extraction_status = 'done'
            """,
            (user_id,),
        ).fetchall()
        sightings = conn.execute(
            """
            SELECT id, photo_id, product_name, brand, price, extras
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
            user_stores=user_stores,
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


def get_photos_extraction_status(user_id: str, image_ids: list[str]) -> list[dict[str, Any]]:
    if not image_ids:
        return []

    placeholders = ",".join("?" for _ in image_ids)
    with _connect() as conn:
        photos = conn.execute(
            f"""
            SELECT id, extraction_status, extraction_error, gps_latitude, gps_longitude,
                   captured_at, store_location_id, type
            FROM photos
            WHERE user_id = ? AND id IN ({placeholders})
            """,
            (user_id, *image_ids),
        ).fetchall()
        sightings = conn.execute(
            f"""
            SELECT photo_id, product_name, brand, price, extras, line_index
            FROM product_sightings
            WHERE user_id = ? AND photo_id IN ({placeholders})
            ORDER BY photo_id, line_index
            """,
            (user_id, *image_ids),
        ).fetchall()

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
        status = photo["extraction_status"]
        products = sightings_by_photo.get(image_id, [])
        product_count = len(products)
        payload: dict[str, Any] = {
            "image_id": image_id,
            "image_path": f"api/media/{image_id}",
            "extraction_status": status,
            "product_count": product_count,
            "products": products,
            "extraction_empty": status == "done" and product_count == 0,
            "meta": {
                "gps_latitude": photo.get("gps_latitude"),
                "gps_longitude": photo.get("gps_longitude"),
                "captured_at": photo.get("captured_at"),
            },
        }
        if photo.get("extraction_error"):
            payload["extraction_error"] = photo["extraction_error"]
        results.append(payload)
    return results


def build_product_row(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    rows = list_product_rows(user_id)
    return next((row for row in rows if row["id"] == sighting_id), None)


def count_sightings_for_user(user_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM product_sightings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["count"]) if row else 0


def captured_at_from_exif_value(raw_dt: str | None) -> str | None:
    return captured_at_from_exif(raw_dt)
