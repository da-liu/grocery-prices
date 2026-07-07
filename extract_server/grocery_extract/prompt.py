"""Prompt used for vision-based grocery product extraction."""

EXTRACTION_SYSTEM = """You extract grocery product and price information from photos of store shelves or receipts.

Return ONLY valid JSON with no markdown, commentary, or trailing text."""

SHELF_RULES = """Extract every distinct product that has a visible price, shelf tag, or package label.

Rules:
- Include one object per distinct product with its own price tag or sticker.
- Use numeric prices only (no $ sign).
- unit_price must be the per-unit shelf tag price (e.g. $/100g, $/lb, $/EA).
- Store any additional information in the other field as key value pairs.
- Do not invent products not visible in the photo."""

RECEIPT_RULES = """Analyze this grocery receipt photo and extract every line item with a price.

Return JSON matching the same products schema as shelf photos.

Rules:
- One object per receipt line item.
- Skip subtotals, tax, payment lines, and store header/footer boilerplate."""


PRODUCT_SCHEMA = """{
  "type": "shelf" | "receipt",
  "products": [
    {
      "product_name": "product name (required)",
      "price": 0.0,
      "unit": "EA | lb | 100g | kg | etc, or null",
      "unit_price": 0.0 | null,
      "category": "short slug, e.g. produce, meat, snacks, pantry",
      "other": {
        "brand": "brand or null",
        "packed_on": "date on label or null",
        "notes": "optional context or null",
        "regular_price": if regular price is shown alongside the sale price,
        "is_special": true | false,
        "barcode": "identifiers or null",
        "net_weight": "0.524 kg | 1.16 lb | null",
        "<key>": "<value> any additional information as key value pairs"
      }
    }
  ]
}"""

UNIFIED_USER = f"""Analyze this grocery image. First decide whether it is a shelf photo or a receipt, then extract products using the matching rules below.

Return JSON matching this schema:
{PRODUCT_SCHEMA}

Classification:
- Set type to "receipt" if it is a printed grocery receipt with line items.
- Otherwise set type to "shelf" store shelves, produce photos.

If type is "shelf", follow these shelf extraction instructions:
{SHELF_RULES}

If type is "receipt", follow these receipt extraction instructions:
{RECEIPT_RULES}

Return both type and products in a single JSON object. Do not omit either field."""


def build_unified_prompt() -> str:
    return f"{EXTRACTION_SYSTEM}\n\n{UNIFIED_USER}"
