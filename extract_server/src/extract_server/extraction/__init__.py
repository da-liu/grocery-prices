"""Grocery price photo extraction pipeline."""

from extract_server.extraction.schema import ExtractionResult, ExtractedProduct

__all__ = ["ExtractionResult", "ExtractedProduct", "extract_from_upload"]


def extract_from_upload(*args, **kwargs):
    from extract_server.extraction.pipeline import extract_from_upload as _extract_from_upload

    return _extract_from_upload(*args, **kwargs)
