"""Unified 1-step classify + extract prompt."""

from __future__ import annotations

from grocery_extract.prompt import EXTRACTION_SYSTEM, EXTRACTION_USER, RECEIPT_USER

PRODUCT_SCHEMA = """{
  "type": "shelf" | "receipt",
  "products": [
    {
      "product_name": "English product name (required)",
      "product_name_zh": "Chinese name if visible, else null",
      "brand": "brand or null",
      "price": 0.0,
      "unit": "EA | lb | 100g | bag | bottle | box | etc, or null",
      "unit_price": null,
      "unit_price_per_100g": null,
      "regular_price": null,
      "is_special": false,
      "promo": "promo text or null",
      "barcode": "digits only or null",
      "size": "package size string or null",
      "net_weight": null,
      "net_weight_lb": null,
      "packed_on": "date on label or null",
      "category": "one of: condiments, dairy-eggs, tofu, dried-goods, pantry, rice, produce, produce-herbs, frozen-seafood, meat, noodles, deli, canned-goods, cereal, snacks, frozen-desserts, pasta, beverages",
      "notes": "optional context or null"
    }
  ]
}"""

UNIFIED_USER = f"""Analyze this grocery image. First decide whether it is a shelf photo or a receipt, then extract products using the matching rules below.

Return JSON matching this schema:
{PRODUCT_SCHEMA}

Classification:
- Set type to "receipt" if it is a printed grocery receipt with line items.
- Otherwise set type to "shelf" (store shelves, deli counters, meat labels, or price tags).

If type is "shelf", follow these shelf extraction instructions:
{EXTRACTION_USER}

If type is "receipt", follow these receipt extraction instructions:
{RECEIPT_USER}

Return both type and products in a single JSON object. Do not omit either field."""


def build_unified_prompt() -> str:
    return f"{EXTRACTION_SYSTEM}\n\n{UNIFIED_USER}"
