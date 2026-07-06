from __future__ import annotations

from typing import Any


def product_match_key(product: dict[str, Any]) -> str | None:
    other = product.get("other")
    barcode = product.get("barcode")
    if not barcode and isinstance(other, dict):
        barcode = other.get("barcode")
    if barcode:
        return f"barcode:{str(barcode).strip()}"
    name = (product.get("product_name") or "").strip().lower()
    if name and name != "no products extracted":
        return f"name:{name}"
    return None


def _captured_ts(product: dict[str, Any]) -> float:
    captured_at = product.get("captured_at")
    if not captured_at:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(captured_at)).timestamp()
    except ValueError:
        return 0.0


def build_price_insights(
    product: dict[str, Any],
    all_products: list[dict[str, Any]],
    *,
    limit: int = 4,
) -> list[dict[str, Any]]:
    key = product_match_key(product)
    if not key:
        return []

    current_store = (product.get("location") or {}).get("store")
    current_price = product.get("price")
    insights: list[dict[str, Any]] = []

    for other in all_products:
        if other.get("id") == product.get("id"):
            continue
        if product_match_key(other) != key:
            continue
        if other.get("price") is None:
            continue

        other_store = (other.get("location") or {}).get("store")
        same_store = current_store and other_store == current_store
        price_delta = None
        if current_price is not None:
            price_delta = round(float(other["price"]) - float(current_price), 2)

        insight_type = "history"
        if same_store:
            insight_type = "same_store_history"
        elif current_store and other_store and other_store != current_store:
            insight_type = "other_store"

        insights.append(
            {
                "product_id": other.get("id"),
                "product_name": other.get("product_name"),
                "price": other.get("price"),
                "store": other_store,
                "captured_at": other.get("captured_at"),
                "image_id": other.get("image_id"),
                "insight_type": insight_type,
                "price_delta": price_delta,
            }
        )

    insights.sort(key=_captured_ts, reverse=True)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, float | None]] = set()
    for insight in insights:
        signature = (insight.get("store"), insight.get("price"))
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(insight)
        if len(deduped) >= limit:
            break

    return deduped


def attach_price_insights(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for product in products:
        row = dict(product)
        insights = build_price_insights(product, products)
        if insights:
            row["price_insights"] = insights
        enriched.append(row)
    return enriched


def products_to_match_rows(
    products: list[dict[str, Any]],
    *,
    image_id: str,
    location: dict[str, Any],
    captured_at: str | None,
) -> list[dict[str, Any]]:
    return [
        {
            "id": f"{image_id}:{index}",
            "image_id": image_id,
            "captured_at": captured_at,
            "location": location,
            **product,
        }
        for index, product in enumerate(products, start=1)
    ]


def overlapping_product_keys(
    new_products: list[dict[str, Any]],
    existing_products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_keys = {
        product_match_key(product): product
        for product in existing_products
        if product_match_key(product)
    }
    overlaps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in new_products:
        key = product_match_key(product)
        if not key or key in seen:
            continue
        existing = existing_keys.get(key)
        if existing is None:
            continue
        seen.add(key)
        overlaps.append(
            {
                "match_key": key,
                "new_product_name": product.get("product_name"),
                "existing_product_id": existing.get("id"),
                "existing_product_name": existing.get("product_name"),
                "existing_price": existing.get("price"),
                "existing_store": (existing.get("location") or {}).get("store"),
                "existing_captured_at": existing.get("captured_at"),
            }
        )
    return overlaps
