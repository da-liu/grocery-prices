from __future__ import annotations

import json
from pathlib import Path

from grocery_extract.stores import store_from_gps
from grocery_extract.user_paths import user_meta_path


def load_meta_by_stem(user_id: str) -> dict[str, dict]:
    path = user_meta_path(user_id)
    if not path.exists():
        return {}
    with path.open() as f:
        return {Path(row["SourceFile"]).stem: row for row in json.load(f)}


def _save_meta_rows(user_id: str, rows: list[dict]) -> None:
    path = user_meta_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")


def get_image_store_location_id(user_id: str, image_id: str) -> str | None:
    meta = load_meta_by_stem(user_id).get(image_id)
    if not meta:
        return None
    value = meta.get("store_location_id")
    return value if isinstance(value, str) and value else None


def set_image_store_location_id(
    user_id: str,
    image_id: str,
    store_location_id: str | None,
) -> bool:
    path = user_meta_path(user_id)
    rows: list[dict]
    if path.exists():
        with path.open() as f:
            rows = json.load(f)
    else:
        rows = []

    replaced = False
    for row in rows:
        if Path(row["SourceFile"]).stem == image_id:
            if store_location_id:
                row["store_location_id"] = store_location_id
            else:
                row.pop("store_location_id", None)
            replaced = True
            break

    if not replaced:
        return False

    _save_meta_rows(user_id, rows)
    return True


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
) -> bool:
    if get_image_store_location_id(user_id, image_id):
        return False
    if lat is not None and lon is not None and store_from_gps(lat, lon, user_stores):
        return False
    return True
