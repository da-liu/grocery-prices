from __future__ import annotations

from extract_server.db import get_photo_store_location_id, set_photo_store_location_id
from extract_server.extraction.stores import store_from_gps


def get_image_store_location_id(user_id: str, image_id: str) -> str | None:
    return get_photo_store_location_id(user_id, image_id)


def set_image_store_location_id(
    user_id: str,
    image_id: str,
    store_location_id: str | None,
) -> bool:
    return set_photo_store_location_id(user_id, image_id, store_location_id)


def auto_assign_store_from_gps(
    user_id: str,
    image_id: str,
    lat: float | None,
    lon: float | None,
    user_stores: list[dict],
) -> str | None:
    if lat is None or lon is None or not user_stores:
        return None
    if get_image_store_location_id(user_id, image_id):
        return get_image_store_location_id(user_id, image_id)

    matched = store_from_gps(lat, lon, user_stores)
    if not matched:
        return None

    store_id = matched["id"]
    set_image_store_location_id(user_id, image_id, store_id)
    return store_id


def image_needs_store_label(
    user_id: str,
    image_id: str,
    lat: float | None,
    lon: float | None,
    user_stores: list[dict],
    *,
    store_location_id: str | None = None,
) -> bool:
    assigned = store_location_id
    if assigned is None:
        assigned = get_image_store_location_id(user_id, image_id)
    if assigned:
        return False
    if lat is not None and lon is not None and store_from_gps(lat, lon, user_stores):
        return False
    return True
