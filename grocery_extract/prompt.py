"""Prompt used for vision-based grocery product extraction."""

EXTRACTION_SYSTEM = """You extract grocery product and price information from photos of store shelves, deli counters, meat labels, or price tags in Toronto-area supermarkets (CAD prices).

Return ONLY valid JSON with no markdown fences, commentary, or trailing text."""

EXTRACTION_USER = """Analyze this grocery store photo and extract every distinct product that has a visible price, shelf tag, or package label.

Return JSON matching this schema:
{
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
}

Rules:
- Include one object per distinct product with its own price tag or sticker.
- Only include products where a price is clearly visible on a tag, sticker, or shelf label. Skip items with no readable price.
- When multiple similar items share one tag (e.g. 4 tomato cans at same price), still list each distinct product name/variant separately if tags distinguish them.
- Use numeric prices only (no $ sign). Use null when price is not visible.
- net_weight and net_weight_lb must be plain numbers (kg or lb), not strings with units.
- Set is_special true when tag shows sale/special/advertised special/was price.
- Set regular_price when a "was" or regular price is shown alongside the sale price.
- For per-weight deli/meat tags priced per 100g or per lb, set unit accordingly and put the tagged unit price in price when that is the primary displayed price.
- For weighed packages, use the total price on the label as price and unit_price as $/kg or $/lb when shown.
- unit_price must be the per-unit shelf tag price (e.g. $/100g, $/lb, $/EA). Never put the package total in unit_price.
- unit_price_per_100g is only for tags that explicitly show price per 100g; leave null otherwise.
- When both total package price and per-unit price appear, price = total package price, unit_price = per-unit rate.
- Read Chinese characters on packaging into product_name_zh when present.
- Do not invent products not visible in the photo."""


RECEIPT_USER = """Analyze this grocery receipt photo and extract every line item with a price.

Return JSON matching the same products schema as shelf photos. Use category "pantry" when unsure.

Rules:
- One object per receipt line item.
- product_name should match the printed item description.
- Use the line total as price when shown; otherwise use the unit price.
- unit_price is the per-unit rate only (e.g. $/kg, $/EA), never the line total.
- Include barcode only when printed on the receipt line.
- Skip subtotals, tax, payment lines, and store header/footer boilerplate."""


def build_prompt() -> str:
    return f"{EXTRACTION_SYSTEM}\n\n{EXTRACTION_USER}"


def build_receipt_prompt() -> str:
    return f"{EXTRACTION_SYSTEM}\n\n{RECEIPT_USER}"
