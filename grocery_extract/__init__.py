"""Grocery price photo extraction pipeline."""

from grocery_extract.schema import ExtractionResult, ExtractedProduct

__all__ = ["ExtractionResult", "ExtractedProduct", "extract_from_upload"]


def extract_from_upload(*args, **kwargs):
    from grocery_extract.pipeline import extract_from_upload as _extract_from_upload

    return _extract_from_upload(*args, **kwargs)
