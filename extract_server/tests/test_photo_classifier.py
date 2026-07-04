from __future__ import annotations

from grocery_extract.photo_classifier import _parse_classification


def test_parse_classification_receipt_json():
    assert _parse_classification('{"type":"receipt"}') == "receipt"


def test_parse_classification_shelf_json():
    assert _parse_classification('{"type":"shelf"}') == "shelf"


def test_parse_classification_fallback_text():
    assert _parse_classification("This looks like a receipt") == "receipt"
    assert _parse_classification("shelf photo") == "shelf"
