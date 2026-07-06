from __future__ import annotations

import pytest

from grocery_extract.parse_response import parse_unified_response


def test_parse_unified_shelf():
    raw = """
    {
      "type": "shelf",
      "products": [
        {"product_name": "Soy Sauce", "price": 3.99, "category": "condiments"}
      ]
    }
    """
    result = parse_unified_response(raw)
    assert result.photo_type == "shelf"
    assert len(result.products) == 1
    assert result.products[0].product_name == "Soy Sauce"


def test_parse_unified_receipt():
    raw = """```json
{
  "type": "receipt",
  "products": [
    {"product_name": "KELLOGGS MINI WHEAT", "price": 5.99, "category": "cereal"}
  ]
}
```"""
    result = parse_unified_response(raw)
    assert result.photo_type == "receipt"
    assert result.products[0].price == 5.99


def test_parse_unified_malformed_type_defaults_shelf():
    raw = '{"type": "unknown", "products": []}'
    result = parse_unified_response(raw)
    assert result.photo_type == "shelf"
    assert result.products == []


def test_parse_unified_missing_products():
    raw = '{"type": "receipt"}'
    result = parse_unified_response(raw)
    assert result.photo_type == "receipt"
    assert result.products == []


def test_parse_unified_top_level_array():
    raw = """[
  {
    "product_name": "Milk",
    "price": 4.99,
    "category": "dairy-eggs"
  },
  {
    "product_name": "Bread",
    "price": 2.99,
    "category": "pantry"
  }
]"""
    result = parse_unified_response(raw)
    assert result.photo_type == "shelf"
    assert len(result.products) == 2


def test_parse_unified_nested_other():
    raw = """
    {
      "type": "shelf",
      "products": [
        {
          "product_name": "Tomatoes",
          "price": 2.49,
          "category": "produce",
          "other": {
            "brand": "Farm Boy",
            "packed_on": "2024-07-01",
            "notes": "Ontario grown"
          }
        }
      ]
    }
    """
    result = parse_unified_response(raw)
    product = result.products[0]
    assert product.other == {
        "brand": "Farm Boy",
        "packed_on": "2024-07-01",
        "notes": "Ontario grown",
    }


def test_parse_unified_invalid_json():
    with pytest.raises(ValueError, match="No JSON found"):
        parse_unified_response("not json at all")
