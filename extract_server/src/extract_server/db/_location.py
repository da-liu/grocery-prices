from __future__ import annotations

from typing import Any

from extract_server.db._ids import empty_sighting_id
from extract_server.db._product_fields import merge_sighting_row
from extract_server.extraction.stores import store_from_gps


def location_for_photo(
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
            "store": store.get("store") or "Unknown store",
            "store_location_id": assigned,
        }
    elif lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            location = {
                "store": matched.get("store") or "Unknown store",
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


def product_line(
    user_id: str,
    photo: dict[str, Any],
    sighting: dict[str, Any] | None,
    location: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "image_id": photo["id"],
        "image_path": f"api/media/{photo['id']}",
        "captured_at": photo.get("captured_at"),
        "location": location,
        "photo_type": photo.get("type") or "shelf",
    }
    if sighting is None:
        return {
            **base,
            "id": empty_sighting_id(user_id, photo["id"]),
            "product_name": "No products extracted",
            "category": "pantry",
            "price": None,
            "extraction_empty": True,
        }
    merged = merge_sighting_row(sighting)
    return {"id": sighting["id"], **base, **merged}


def extraction_status(extraction: dict[str, Any] | None) -> str:
    if extraction is None:
        return "pending"
    if extraction.get("extraction_error"):
        return "failed"
    pipeline = pipeline_status(extraction)
    if pipeline in {"extracted", "matched", "match_failed"}:
        return "done"
    return "done"


def pipeline_status(extraction: dict[str, Any] | None) -> str:
    if extraction is None:
        return "pending"
    if extraction.get("extraction_error"):
        return "failed"
    status = extraction.get("status")
    if status in {"extracted", "matched", "failed", "match_failed"}:
        return status
    return "matched"
