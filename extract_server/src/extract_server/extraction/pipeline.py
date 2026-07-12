from __future__ import annotations

from pathlib import Path

from extract_server.extraction.gemini_extractor import current_extractor_name, extract_products_from_image
from extract_server.extraction.schema import ExtractionResult, ExtractionTiming


def extract_from_upload(
    image_path: Path,
    *,
    api_key: str | None = None,
) -> ExtractionResult:
    """Extract products from a persisted image file via Gemini."""
    products_result = extract_products_from_image(
        image_path,
        api_key=api_key,
    )
    return ExtractionResult(
        image_path=str(image_path),
        products=products_result.products,
        photo_type=products_result.photo_type,
        raw_response=products_result.raw_response,
        extractor=current_extractor_name(),
        timing=ExtractionTiming(
            llm_ms=products_result.llm_ms,
            other_ms=products_result.other_ms,
            model=products_result.model,
        ),
    )
