from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from grocery_extract.delete import delete_photo, parse_product_id
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.products_builder import write_user_products_jsonl
from grocery_extract.schema import ExtractedProduct
from grocery_extract.user_paths import find_user_jpg, user_extractions_dir

TORONTO = ZoneInfo("America/Toronto")

EDITABLE_FIELDS = {
    "product_name",
    "product_name_zh",
    "brand",
    "price",
    "unit",
    "unit_price",
    "unit_price_per_100g",
    "regular_price",
    "is_special",
    "promo",
    "barcode",
    "size",
    "category",
    "notes",
}


def _load_extraction(user_id: str, image_id: str) -> dict | None:
    path = user_extractions_dir(user_id) / f"{image_id}.json"
    if not path.exists():
        return None
    with path.open() as handle:
        return json.load(handle)


def _save_extraction(user_id: str, image_id: str, payload: dict) -> None:
    path = user_extractions_dir(user_id) / f"{image_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def update_product(user_id: str, product_id: str, updates: dict) -> dict | None:
    parsed = parse_product_id(product_id)
    if parsed is None:
        return None

    image_id, idx = parsed
    payload = _load_extraction(user_id, image_id)
    if payload is None:
        return None

    products = payload.get("products", [])
    product_index = idx - 1
    if product_index < 0 or product_index >= len(products):
        return None

    product = dict(products[product_index])
    for key, value in updates.items():
        if key not in EDITABLE_FIELDS:
            continue
        if value is None and key in {"price", "regular_price", "unit_price", "unit_price_per_100g"}:
            product[key] = None
        elif value is not None:
            product[key] = value

    products[product_index] = product
    payload["products"] = products
    payload["manually_edited_at"] = datetime.now(TORONTO).isoformat(timespec="seconds")
    _save_extraction(user_id, image_id, payload)
    write_user_products_jsonl(user_id)

    from grocery_extract.products_builder import build_product_lines

    lines = build_product_lines(user_id=user_id)
    return next((row for row in lines if row["id"] == product_id), None)


def add_product(user_id: str, image_id: str, product: dict) -> dict | None:
    if not image_id.startswith("IMG_"):
        return None

    payload = _load_extraction(user_id, image_id)
    if payload is None:
        payload = {
            "image_id": image_id,
            "user_id": user_id,
            "source": "manual",
            "extracted_at": datetime.now(TORONTO).isoformat(timespec="seconds"),
            "extractor": "manual",
            "products": [],
        }

    cleaned = {key: value for key, value in product.items() if key in EDITABLE_FIELDS and value is not None}
    if not cleaned.get("product_name"):
        return None
    if not cleaned.get("category"):
        cleaned["category"] = "pantry"

    try:
        ExtractedProduct.model_validate(cleaned)
    except Exception:
        return None

    products = payload.get("products", [])
    products.append(cleaned)
    payload["products"] = products
    _save_extraction(user_id, image_id, payload)
    write_user_products_jsonl(user_id)

    from grocery_extract.products_builder import build_product_lines

    lines = build_product_lines(user_id=user_id)
    new_id = f"{image_id}-{len(products)}"
    return next((row for row in lines if row["id"] == new_id), None)


def reextract_photo(user_id: str, image_id: str, *, api_key: str | None = None) -> dict | None:
    if not image_id.startswith("IMG_"):
        return None

    jpg_path = find_user_jpg(user_id, image_id)
    if jpg_path is None or not jpg_path.exists():
        return None

    payload = _load_extraction(user_id, image_id)
    if payload is None:
        return None

    source = payload.get("source", "upload")
    prompt_variant = "receipt" if source == "receipt" else "shelf"
    result = extract_from_upload(
        jpg_path,
        image_id=image_id,
        api_key=api_key,
        prompt_variant=prompt_variant,
    )

    payload["products"] = [product.to_product_dict() for product in result.products]
    payload["extracted_at"] = datetime.now(TORONTO).isoformat(timespec="seconds")
    payload["extractor"] = result.extractor
    payload["reextracted_at"] = datetime.now(TORONTO).isoformat(timespec="seconds")
    _save_extraction(user_id, image_id, payload)
    product_count = write_user_products_jsonl(user_id)

    from grocery_extract.product_matching import overlapping_product_keys
    from grocery_extract.products_builder import build_product_lines

    all_products = build_product_lines(user_id=user_id)
    new_rows = [row for row in all_products if row["image_id"] == image_id]
    existing_rows = [row for row in all_products if row["image_id"] != image_id]
    overlaps = overlapping_product_keys(new_rows, existing_rows)

    return {
        "image_id": image_id,
        "products": payload["products"],
        "product_count": product_count,
        "overlapping_products": overlaps,
        "extraction_empty": len(payload["products"]) == 0,
    }
