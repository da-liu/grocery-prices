from __future__ import annotations

import json
from pathlib import Path

from grocery_extract.exif import captured_at_from_exif, date_folder_from_exif
from grocery_extract.photo_stores import get_image_store_location_id
from grocery_extract.stores import load_stores, store_from_gps
from grocery_extract.user_paths import (
    user_extractions_dir,
    user_meta_path,
    user_photos_dir,
    user_products_path,
    user_root,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
META_PATH = ROOT / ".meta.json"
STORES_PATH = DATA_DIR / "stores.json"
OUT_PATH = DATA_DIR / "products.jsonl"
EXTRACTIONS_DIR = DATA_DIR / "extractions"

DEFAULT_STORE_ID = "hua_sheng"


def location_from_store_record(store: dict) -> dict:
    location = {
        "store": store.get("store") or store.get("name") or "Unknown store",
    }
    if maps_url := store.get("maps_url"):
        location["maps_url"] = maps_url
    if store_id := store.get("id"):
        location["store_location_id"] = store_id
    return location


def location_from_store(store: dict) -> dict:
    return location_from_store_record(store)


def unknown_location() -> dict:
    return {
        "store": "Unknown store",
    }


def store_id_for_image(image_id: str, product: dict) -> str:
    override = product.get("location_override")
    if override:
        return override
    if "IMG_2044" <= image_id <= "IMG_2052":
        return "lucky_moose"
    if image_id >= "IMG_2053":
        return "longos"
    return DEFAULT_STORE_ID


def find_image_path(image_id: str, date_folder: str | None, *, user_id: str | None = None) -> str:
    if user_id:
        photos_root = user_root(user_id) / "photos"
        if date_folder:
            rel = f"api/media/{image_id}"
            if (photos_root / date_folder / "jpg" / f"{image_id}.jpg").exists():
                return rel
        for batch_dir in sorted(photos_root.glob("20*")):
            if (batch_dir / "jpg" / f"{image_id}.jpg").exists():
                return f"api/media/{image_id}"
        return f"api/media/{image_id}"

    if date_folder:
        rel = f"data/{date_folder}/jpg/{image_id}.jpg"
        if (DATA_DIR / date_folder / "jpg" / f"{image_id}.jpg").exists():
            return rel
    for batch_dir in sorted(DATA_DIR.glob("20*")):
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            return f"data/{batch_dir.name}/jpg/{image_id}.jpg"
    if date_folder:
        return f"data/{date_folder}/jpg/{image_id}.jpg"
    return f"data/jpg/{image_id}.jpg"


def store_for_image(
    image_id: str,
    product: dict,
    lat: float | None,
    lon: float | None,
    *,
    stores: list[dict] | None = None,
    store_by_id: dict[str, dict] | None = None,
    user_stores: list[dict] | None = None,
    user_store_by_id: dict[str, dict] | None = None,
    assigned_store_id: str | None = None,
    user_scoped: bool = False,
) -> dict:
    user_store_by_id = user_store_by_id or (
        {store["id"]: store for store in user_stores} if user_stores else {}
    )

    if assigned_store_id and assigned_store_id in user_store_by_id:
        return location_from_store_record(user_store_by_id[assigned_store_id])

    if lat is not None and lon is not None and user_stores:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            return location_from_store_record(matched)

    if user_scoped:
        override = product.get("location_override")
        if override:
            loaded_stores, loaded_by_id = load_stores()
            if override in loaded_by_id:
                return location_from_store(loaded_by_id[override])
        return unknown_location()

    loaded_stores, loaded_by_id = load_stores()
    stores = stores or loaded_stores
    store_by_id = store_by_id or loaded_by_id

    if lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, stores)
        if matched:
            return location_from_store(matched)

    store_id = store_id_for_image(image_id, product)
    return location_from_store(store_by_id[store_id])


def load_meta_by_stem(meta_path: Path = META_PATH) -> dict[str, dict]:
    if not meta_path.exists():
        return {}
    with meta_path.open() as f:
        return {Path(row["SourceFile"]).stem: row for row in json.load(f)}


def load_extractions(extractions_dir: Path = EXTRACTIONS_DIR) -> dict[str, list[dict]]:
    if not extractions_dir.exists():
        return {}
    merged: dict[str, list[dict]] = {}
    for path in sorted(extractions_dir.glob("IMG_*.json")):
        with path.open() as f:
            payload = json.load(f)
        products = payload.get("products", [])
        if products:
            merged[path.stem] = products
    return merged


def build_product_lines(
    manual_products: dict[str, list[dict]],
    *,
    include_extractions: bool = True,
    user_id: str | None = None,
) -> list[dict]:
    """Merge manual extractions with saved vision pipeline results."""
    if user_id:
        products_by_image = load_extractions(user_extractions_dir(user_id))
        meta_by_stem = load_meta_by_stem(user_meta_path(user_id))
    else:
        products_by_image = dict(manual_products)
        if include_extractions:
            for image_id, products in load_extractions().items():
                products_by_image[image_id] = products
        meta_by_stem = load_meta_by_stem()

    stores, store_by_id = load_stores()
    user_stores: list[dict] = []
    user_store_by_id: dict[str, dict] = {}
    if user_id:
        from grocery_extract.user_stores_db import list_user_stores_as_dicts

        user_stores = list_user_stores_as_dicts(user_id)
        user_store_by_id = {store["id"]: store for store in user_stores}

    lines: list[dict] = []

    for image_id, products in sorted(products_by_image.items()):
        meta = meta_by_stem.get(image_id, {})
        lat = meta.get("GPSLatitude")
        lon = meta.get("GPSLongitude")
        assigned_store_id = get_image_store_location_id(user_id, image_id) if user_id else None
        raw_dt = meta.get("DateTimeOriginal")
        captured_at = captured_at_from_exif(raw_dt)
        date_folder = date_folder_from_exif(raw_dt)

        for idx, raw in enumerate(products, start=1):
            product = dict(raw)
            location = store_for_image(
                image_id,
                product,
                lat,
                lon,
                stores=stores,
                store_by_id=store_by_id,
                user_stores=user_stores,
                user_store_by_id=user_store_by_id,
                assigned_store_id=assigned_store_id,
                user_scoped=bool(user_id),
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
                **{k: v for k, v in product.items() if k != "location_override"},
            }
            lines.append(entry)

    return lines


def write_user_products_jsonl(user_id: str) -> int:
    lines = build_product_lines({}, user_id=user_id)
    out_path = user_products_path(user_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(lines)


def write_products_jsonl(
    manual_products: dict[str, list[dict]],
    *,
    out_path: Path | None = None,
    viewer_public: Path | None = None,
) -> int:
    lines = build_product_lines(manual_products)
    out_path = out_path or OUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    viewer_public = viewer_public or ROOT / "viewer" / "public" / "products.jsonl"
    viewer_public.parent.mkdir(parents=True, exist_ok=True)
    viewer_public.write_text(out_path.read_text())
    return len(lines)
