from __future__ import annotations

import json
from typing import Any

from extract_server.grocery_extract.schema import ExtractedProduct, fold_product_fields

EDITABLE_FIELDS = frozenset(
    {"product_name", "other", "price", "unit", "unit_price", "category"}
)


def normalize_other(product: dict[str, Any]) -> dict[str, Any]:
    folded = fold_product_fields(product)
    other = dict(folded.get("other") or {})
    for key in ("unit", "unit_price", "category"):
        if key in folded:
            if folded[key] is None:
                other.pop(key, None)
            else:
                other[key] = folded[key]
    if other.get("is_special") is False:
        other.pop("is_special", None)
    return other


def split_product_fields(
    product: dict[str, Any],
) -> tuple[str, float | None, dict[str, Any]]:
    product_name = str(product["product_name"])
    price = product.get("price")
    return product_name, price, normalize_other(product)


def merge_sighting_row(row: Any) -> dict[str, Any]:
    other = dict(json.loads(row["other"] or "{}"))
    return {
        "product_name": row["product_name"],
        "price": row["price"],
        **other,
        "other": other,
    }


def validate_product(product: dict[str, Any]) -> bool:
    try:
        ExtractedProduct.model_validate(product)
    except Exception:
        return False
    return True
