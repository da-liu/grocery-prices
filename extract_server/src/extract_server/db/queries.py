from __future__ import annotations

import sqlite3
from typing import Any

from extract_server.db._helpers import one
from extract_server.db._location import extraction_status, location_for_photo, pipeline_status, product_line
from extract_server.db._product_fields import merge_sighting_row
from extract_server.db.connection import get_conn
from extract_server.db.extractions import extraction_timing_payload
from extract_server.db.user_stores import list_user_stores_as_dicts


def list_product_rows(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    db = conn or get_conn()
    user_stores = list_user_stores_as_dicts(user_id, conn=db)
    user_store_by_id = {store["id"]: store for store in user_stores}

    from extract_server.db.similarity import load_relations_by_source

    relations_by_source = load_relations_by_source(user_id, conn=db)

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
        location = location_for_photo(
            photo_dict,
            user_stores=user_stores,
            user_store_by_id=user_store_by_id,
        )
        photo_sightings = sightings_by_photo.get(photo_dict["id"], [])
        if not photo_sightings:
            lines.append(product_line(user_id, photo_dict, None, location))
            continue
        for row in photo_sightings:
            line = product_line(user_id, photo_dict, dict(row), location)
            related = relations_by_source.get(row["id"])
            if related:
                line["related_products"] = related
            lines.append(line)

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
        SELECT photo_id, llm_ms, other_ms, model, extraction_error, status
        FROM extractions
        WHERE user_id = ? AND photo_id IN ({placeholders})
        """,
        (user_id, *image_ids),
    ).fetchall()

    extraction_by_photo = {row["photo_id"]: dict(row) for row in extractions}
    sightings_by_photo: dict[str, list[dict[str, Any]]] = {}
    for row in sightings:
        merged = merge_sighting_row(row)
        sightings_by_photo.setdefault(row["photo_id"], []).append(merged)

    photo_by_id = {row["id"]: dict(row) for row in photos}
    results: list[dict[str, Any]] = []
    for image_id in image_ids:
        photo = photo_by_id.get(image_id)
        if photo is None:
            continue
        extraction = extraction_by_photo.get(image_id)
        status = extraction_status(extraction)
        pipeline = pipeline_status(extraction)
        products = sightings_by_photo.get(image_id, [])
        product_count = len(products)
        payload: dict[str, Any] = {
            "image_id": image_id,
            "image_path": f"api/media/{image_id}",
            "status": pipeline,
            "extraction_status": status,
            "detected_receipt": False,
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
        photo_type = photo.get("type")
        if isinstance(photo_type, str) and photo_type:
            payload["photo_type"] = photo_type
            payload["detected_receipt"] = photo_type == "receipt"
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


def build_product_row(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    sighting = one(
        conn,
        """
        SELECT id, photo_id, line_index, product_name, price, other
        FROM product_sightings
        WHERE user_id = ? AND id = ?
        """,
        (user_id, sighting_id),
    )
    if sighting is None:
        return None

    photo = one(
        conn,
        """
        SELECT p.id, p.type, p.gps_latitude, p.gps_longitude, p.captured_at, p.store_location_id
        FROM photos p
        INNER JOIN extractions e ON e.user_id = p.user_id AND e.photo_id = p.id
        WHERE p.user_id = ? AND p.id = ? AND e.extraction_error IS NULL
        """,
        (user_id, sighting["photo_id"]),
    )
    if photo is None:
        return None

    user_stores = list_user_stores_as_dicts(user_id, conn=conn)
    user_store_by_id = {store["id"]: store for store in user_stores}
    location = location_for_photo(
        photo,
        user_stores=user_stores,
        user_store_by_id=user_store_by_id,
    )
    line = product_line(user_id, photo, sighting, location)
    from extract_server.db.similarity import load_relations_by_source

    related = load_relations_by_source(user_id, conn=conn).get(sighting_id)
    if related:
        line["related_products"] = related
    return line
