from __future__ import annotations

import json
import re
from typing import Any

from grocery_extract.schema import ExtractedProduct


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"[-+]?\d*\.?\d+", value.replace(",", ""))
        if match:
            return float(match.group())
    return None


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(row)
    for key in ("price", "unit_price", "unit_price_per_100g", "regular_price", "net_weight", "net_weight_lb"):
        if key in cleaned:
            cleaned[key] = _coerce_float(cleaned[key])
    if cleaned.get("is_special") is None:
        cleaned.pop("is_special", None)
    if cleaned.get("barcode") is not None:
        cleaned["barcode"] = re.sub(r"\D", "", str(cleaned["barcode"])) or None
    return cleaned


def parse_products_json(text: str) -> list[ExtractedProduct]:
    cleaned = _strip_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    payload: dict[str, Any] = json.loads(cleaned[start : end + 1])
    rows = payload.get("products", payload if isinstance(payload, list) else [])
    if not isinstance(rows, list):
        raise ValueError("Expected products array in JSON response")
    products: list[ExtractedProduct] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row = _sanitize_row(row)
        if not row.get("product_name") or not row.get("category"):
            continue
        products.append(ExtractedProduct.model_validate(row))
    return products
