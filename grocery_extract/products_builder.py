from __future__ import annotations

from grocery_extract.catalog_db import list_product_rows


def build_product_lines(*, user_id: str) -> list[dict]:
    return list_product_rows(user_id)
