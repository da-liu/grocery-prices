"""Parse unified classify + extract LLM responses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from grocery_extract.parse_response import parse_products_json


@dataclass(frozen=True)
class UnifiedExtraction:
    photo_type: str
    products: list[dict]


def _normalize_type(value: Any) -> str:
    text = str(value or "shelf").strip().lower()
    return "receipt" if text == "receipt" else "shelf"


def parse_unified_response(raw: str) -> UnifiedExtraction:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in unified model response")

    payload: dict[str, Any] = json.loads(text[start : end + 1])
    photo_type = _normalize_type(payload.get("type"))

    if "products" in payload:
        products_payload = json.dumps({"products": payload["products"]})
        products = [p.to_product_dict() for p in parse_products_json(products_payload)]
    else:
        products = []

    return UnifiedExtraction(photo_type=photo_type, products=products)
