from __future__ import annotations

import json
from pathlib import Path

from grocery_extract.exif import captured_at_from_exif, date_folder_from_exif
from grocery_extract.photo_stores import get_image_store_location_id
from grocery_extract.product_matching import attach_price_insights
from grocery_extract.stores import store_from_gps
from grocery_extract.user_paths import (
    user_extractions_dir,
    user_meta_path,
    user_products_path,
    user_root,
)


def location_from_store_record(store: dict) -> dict:
    location = {
        "store": store.get("store") or store.get("name") or "Unknown store",
    }
    if maps_url := store.get("maps_url"):
        location["maps_url"] = maps_url
    if store_id := store.get("id"):
        location["store_location_id"] = store_id
    return location


def unknown_location() -> dict:
    return {
        "store": "Unknown store",
    }


def find_image_path(image_id: str, date_folder: str | None, *, user_id: str) -> str:
    photos_root = user_root(user_id) / "photos"
    if date_folder:
        rel = f"api/media/{image_id}"
        if (photos_root / date_folder / "jpg" / f"{image_id}.jpg").exists():
            return rel
    for batch_dir in sorted(photos_root.glob("20*")):
        if (batch_dir / "jpg" / f"{image_id}.jpg").exists():
            return f"api/media/{image_id}"
    return f"api/media/{image_id}"


def store_for_image(
    lat: float | None,
    lon: float | None,
    *,
    user_stores: list[dict] | None = None,
    user_store_by_id: dict[str, dict] | None = None,
    assigned_store_id: str | None = None,
) -> dict:
    user_stores = user_stores or []
    user_store_by_id = user_store_by_id or {store["id"]: store for store in user_stores}

    if assigned_store_id and assigned_store_id in user_store_by_id:
        return location_from_store_record(user_store_by_id[assigned_store_id])

    if lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            return location_from_store_record(matched)

    return unknown_location()


def load_meta_by_stem(meta_path: Path) -> dict[str, dict]:
    if not meta_path.exists():
        return {}
    with meta_path.open() as f:
        return {Path(row["SourceFile"]).stem: row for row in json.load(f)}


def load_extractions(extractions_dir: Path) -> dict[str, list[dict]]:
    if not extractions_dir.exists():
        return {}
    merged: dict[str, list[dict]] = {}
    for path in sorted(extractions_dir.glob("IMG_*.json")):
        with path.open() as f:
            payload = json.load(f)
        merged[path.stem] = payload.get("products", [])
    return merged


def build_product_lines(*, user_id: str) -> list[dict]:
    """Build catalog rows from a user's saved extractions and photo metadata."""
    products_by_image = load_extractions(user_extractions_dir(user_id))
    meta_by_stem = load_meta_by_stem(user_meta_path(user_id))

    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)
    user_store_by_id = {store["id"]: store for store in user_stores}

    lines: list[dict] = []

    for image_id, products in sorted(products_by_image.items()):
        meta = meta_by_stem.get(image_id, {})
        lat = meta.get("GPSLatitude")
        lon = meta.get("GPSLongitude")
        assigned_store_id = get_image_store_location_id(user_id, image_id)
        raw_dt = meta.get("DateTimeOriginal")
        captured_at = captured_at_from_exif(raw_dt)
        date_folder = date_folder_from_exif(raw_dt)

        if not products:
            location = store_for_image(
                lat,
                lon,
                user_stores=user_stores,
                user_store_by_id=user_store_by_id,
                assigned_store_id=assigned_store_id,
            )
            if lat is not None and lon is not None:
                location["latitude"] = lat
                location["longitude"] = lon
            lines.append(
                {
                    "id": f"{image_id}-empty",
                    "image_id": image_id,
                    "image_path": find_image_path(image_id, date_folder, user_id=user_id),
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

        for idx, raw in enumerate(products, start=1):
            product = {
                k: v for k, v in dict(raw).items() if k != "location_override"
            }
            location = store_for_image(
                lat,
                lon,
                user_stores=user_stores,
                user_store_by_id=user_store_by_id,
                assigned_store_id=assigned_store_id,
            )
            if lat is not None and lon is not None:
                location["latitude"] = lat
                location["longitude"] = lon

            entry = {
                "id": f"{image_id}-{idx}",
                "image_id": image_id,
                "image_path": find_image_path(image_id, date_folder, user_id=user_id),
                "price_currency": "CAD",
                "captured_at": captured_at,
                "location": location,
                **product,
            }
            lines.append(entry)

    return attach_price_insights(lines)


def write_user_products_jsonl(user_id: str) -> int:
    lines = build_product_lines(user_id=user_id)
    out_path = user_products_path(user_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(lines)
