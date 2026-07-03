from __future__ import annotations

from grocery_extract.catalog_db import (
    delete_photo as delete_photo_row,
    delete_sighting,
    delete_sightings_bulk,
    prune_orphan_photo_files,
)

__all__ = [
    "delete_photo",
    "delete_product",
    "delete_products_bulk",
    "prune_orphan_photos",
]


def delete_photo(user_id: str, image_id: str) -> bool:
    return delete_photo_row(user_id, image_id)


def delete_product(user_id: str, product_id: str) -> bool:
    return delete_sighting(user_id, product_id)


def delete_products_bulk(user_id: str, product_ids: list[str]) -> dict:
    return delete_sightings_bulk(user_id, product_ids)


def prune_orphan_photos(user_id: str) -> int:
    return prune_orphan_photo_files(user_id)
