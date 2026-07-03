from __future__ import annotations

from grocery_extract.catalog_db import (
    add_sighting,
    get_extraction,
    get_photo,
    list_product_rows,
    replace_photo_extraction,
    update_sighting,
)
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.schema import ExtractedProduct
from grocery_extract.user_paths import find_user_jpg

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


def update_product(user_id: str, product_id: str, updates: dict) -> dict | None:
    filtered = {key: value for key, value in updates.items() if key in EDITABLE_FIELDS}
    if not filtered:
        return None
    return update_sighting(user_id, product_id, filtered)


def add_product(user_id: str, image_id: str, product: dict) -> dict | None:
    if not image_id.startswith("IMG_"):
        return None
    if get_photo(user_id, image_id) is None:
        return None

    cleaned = {key: value for key, value in product.items() if key in EDITABLE_FIELDS and value is not None}
    if not cleaned.get("product_name"):
        return None
    if not cleaned.get("category"):
        cleaned["category"] = "pantry"

    try:
        ExtractedProduct.model_validate(cleaned)
    except Exception:
        return None

    return add_sighting(user_id, image_id, cleaned)


def reextract_photo(user_id: str, image_id: str, *, api_key: str | None = None) -> dict | None:
    if not image_id.startswith("IMG_"):
        return None

    jpg_path = find_user_jpg(user_id, image_id)
    if jpg_path is None or not jpg_path.exists():
        return None

    photo = get_photo(user_id, image_id)
    extraction = get_extraction(user_id, image_id)
    if photo is None or extraction is None:
        return None

    prompt_variant = "receipt" if photo["type"] == "receipt" else "shelf"
    result = extract_from_upload(
        jpg_path,
        image_id=image_id,
        api_key=api_key,
        prompt_variant=prompt_variant,
        skip_normalize=True,
    )

    products = [product.to_product_dict() for product in result.products]
    product_count = replace_photo_extraction(
        user_id,
        image_id,
        extractor=result.extractor,
        raw_response=result.raw_response,
        products=products,
        reextracted=True,
    )

    from grocery_extract.product_matching import overlapping_product_keys

    all_products = list_product_rows(user_id=user_id)
    new_rows = [row for row in all_products if row["image_id"] == image_id]
    existing_rows = [row for row in all_products if row["image_id"] != image_id]
    overlaps = overlapping_product_keys(new_rows, existing_rows)

    return {
        "image_id": image_id,
        "products": products,
        "product_count": product_count,
        "overlapping_products": overlaps,
        "extraction_empty": len(products) == 0,
    }
