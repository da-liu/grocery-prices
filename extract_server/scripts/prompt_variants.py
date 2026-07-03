"""Prompt variants for extraction experiments."""

from __future__ import annotations

from grocery_extract.prompt import EXTRACTION_SYSTEM, EXTRACTION_USER, build_prompt

MINIMAL_SCHEMA_USER = """Analyze this grocery store photo and extract every distinct product with a visible price tag.

Return JSON only:
{
  "products": [
    {
      "product_name": "English name (required)",
      "price": 0.0,
      "category": "condiments | dairy-eggs | tofu | dried-goods | pantry | rice | produce | produce-herbs | frozen-seafood | meat | noodles | deli | canned-goods | cereal | snacks | frozen-desserts | pasta | beverages",
      "barcode": "digits only or null"
    }
  ]
}

Rules:
- One object per priced product visible on a shelf tag or package label.
- Numeric prices only. Use null when price is not readable.
- Do not invent products."""

CONCISE_USER = """Extract every distinct grocery product with a visible price tag from this shelf photo (Toronto supermarket, CAD).

Return JSON only:
{"products":[{"product_name":"...","product_name_zh":null,"brand":null,"price":0.0,"unit":null,"unit_price":null,"unit_price_per_100g":null,"regular_price":null,"is_special":false,"promo":null,"barcode":null,"size":null,"net_weight":null,"net_weight_lb":null,"packed_on":null,"category":"pantry","notes":null}]}

Rules:
- One product per visible price tag. Skip items with no readable price.
- Numeric prices only. is_special true for sale tags.
- unit_price is per-unit rate ($/EA, $/lb, $/100g), never the package total.
- Read Chinese packaging into product_name_zh when visible.
- Do not invent products."""

OCR_FOCUS_USER = """You are an OCR specialist for grocery shelf price tags. Read tags literally; do not guess.

Return ONLY valid JSON:
{
  "products": [
    {
      "product_name": "English product name (required)",
      "product_name_zh": "Chinese name if visible, else null",
      "brand": "brand or null",
      "price": 0.0,
      "unit": "EA | lb | 100g | etc, or null",
      "unit_price": null,
      "unit_price_per_100g": null,
      "regular_price": null,
      "is_special": false,
      "promo": "promo text or null",
      "barcode": "digits only or null",
      "size": "package size or null",
      "category": "condiments | dairy-eggs | tofu | dried-goods | pantry | rice | produce | produce-herbs | frozen-seafood | meat | noodles | deli | canned-goods | cereal | snacks | frozen-desserts | pasta | beverages",
      "notes": null
    }
  ]
}

Rules:
- Transcribe price digits exactly as printed on the tag. Double-check decimal points.
- If a digit is ambiguous, prefer null over guessing.
- Include a product only when a price is clearly visible on a tag, sticker, or shelf label.
- For multi-buy promos (e.g. 2 for $5), set promo text and use the primary displayed price.
- Do not merge separate tags into one product.
- Do not invent products not visible in the photo."""

PROMPT_VARIANTS: dict[str, str] = {
    "baseline": build_prompt(),
    "concise": f"{EXTRACTION_SYSTEM}\n\n{CONCISE_USER}",
    "ocr_focus": f"{EXTRACTION_SYSTEM}\n\n{OCR_FOCUS_USER}",
    "minimal_schema": f"{EXTRACTION_SYSTEM}\n\n{MINIMAL_SCHEMA_USER}",
}
