from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from extract_server.grocery_extract.schema import ExtractedProduct, fold_product_fields


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


def _sanitize_other(other: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in other.items() if value is not None}
    if "regular_price" in cleaned:
        cleaned["regular_price"] = _coerce_float(cleaned["regular_price"])
    if cleaned.get("is_special") is False:
        cleaned.pop("is_special", None)
    if cleaned.get("barcode") is not None:
        cleaned["barcode"] = re.sub(r"\D", "", str(cleaned["barcode"])) or None
        if not cleaned["barcode"]:
            cleaned.pop("barcode", None)
    return cleaned


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = fold_product_fields(row)
    if isinstance(cleaned.get("other"), dict):
        cleaned["other"] = _sanitize_other(cleaned["other"])
        if not cleaned["other"]:
            cleaned.pop("other")
    for key in ("price", "unit_price"):
        if key in cleaned:
            cleaned[key] = _coerce_float(cleaned[key])
    return cleaned


def _normalize_type(value: Any) -> str:
    text = str(value or "shelf").strip().lower()
    return "receipt" if text == "receipt" else "shelf"


def _parse_json_payload(text: str) -> Any:
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start : end + 1])
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            return json.loads(cleaned[start : end + 1])
        raise ValueError("No JSON found in model response") from None


def _rows_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("products", [])
        if isinstance(rows, list):
            return rows
    raise ValueError("Expected products array in JSON response")


def _products_from_rows(rows: list[Any]) -> list[ExtractedProduct]:
    products: list[ExtractedProduct] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row = _sanitize_row(row)
        if not row.get("product_name") or not row.get("category"):
            continue
        products.append(ExtractedProduct.model_validate(row))
    return products


def parse_products_json(text: str) -> list[ExtractedProduct]:
    return _products_from_rows(_rows_from_payload(_parse_json_payload(text)))


@dataclass(frozen=True)
class UnifiedExtraction:
    photo_type: str
    products: list[ExtractedProduct]


def parse_unified_response(raw: str) -> UnifiedExtraction:
    payload = _parse_json_payload(raw)
    photo_type = "shelf"
    if isinstance(payload, dict):
        photo_type = _normalize_type(payload.get("type"))
    rows = _rows_from_payload(payload)
    return UnifiedExtraction(photo_type=photo_type, products=_products_from_rows(rows))
