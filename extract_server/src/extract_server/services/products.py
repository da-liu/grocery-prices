from __future__ import annotations

from extract_server.db._ids import is_valid_photo_id
from extract_server.db._product_fields import EDITABLE_FIELDS, validate_product
from extract_server.db.extractions import (
    get_extraction,
    replace_photo_extraction,
)
from extract_server.db.photos import get_photo, get_photo_blob_path
from extract_server.db.sightings import add_sighting, update_sighting
from extract_server.extraction.pipeline import extract_from_upload


def update_product(user_id: str, product_id: str, updates: dict) -> dict | None:
    filtered = {key: value for key, value in updates.items() if key in EDITABLE_FIELDS}
    if not filtered:
        return None
    return update_sighting(user_id, product_id, filtered)


def add_product(user_id: str, image_id: str, product: dict) -> dict | None:
    if not is_valid_photo_id(image_id):
        return None
    if get_photo(user_id, image_id) is None:
        return None

    cleaned = {key: value for key, value in product.items() if key in EDITABLE_FIELDS and value is not None}
    if not cleaned.get("product_name"):
        return None
    if not cleaned.get("category"):
        cleaned["category"] = "pantry"
    if not validate_product(cleaned):
        return None

    return add_sighting(user_id, image_id, cleaned)


def reextract_photo(
    user_id: str,
    image_id: str,
    *,
    api_key: str | None = None,
) -> dict | None:
    if not is_valid_photo_id(image_id):
        return None

    jpg_path = get_photo_blob_path(user_id, image_id)
    if jpg_path is None or not jpg_path.exists():
        return None

    photo = get_photo(user_id, image_id)
    extraction = get_extraction(user_id, image_id)
    if photo is None or extraction is None:
        return None

    result = extract_from_upload(
        jpg_path,
        api_key=api_key,
    )

    products = [product.to_product_dict() for product in result.products]
    timing = result.timing
    product_count = replace_photo_extraction(
        user_id,
        image_id,
        extractor=result.extractor,
        raw_response=result.raw_response,
        products=products,
        reextracted=True,
        llm_ms=timing.llm_ms if timing else None,
        other_ms=timing.other_ms if timing else None,
        model=timing.model if timing else None,
        photo_type=result.photo_type,
    )

    try:
        from extract_server.db import set_extraction_pipeline_status
        from extract_server.extraction.match_catalog import match_photo

        if product_count > 0:
            set_extraction_pipeline_status(user_id, image_id, "extracted")
            match_photo(user_id, image_id, api_key=api_key)
            set_extraction_pipeline_status(user_id, image_id, "matched")
        else:
            set_extraction_pipeline_status(user_id, image_id, "matched")
    except Exception:
        if product_count > 0:
            from extract_server.db import set_extraction_pipeline_status

            set_extraction_pipeline_status(user_id, image_id, "match_failed")

    return {
        "image_id": image_id,
        "products": products,
        "product_count": product_count,
        "extraction_empty": len(products) == 0,
    }
