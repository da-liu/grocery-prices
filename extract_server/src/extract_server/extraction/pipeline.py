from __future__ import annotations

from pathlib import Path
from typing import Any

from extract_server.extraction.cursor_extractor import current_extractor_name, extract_products_from_image
from extract_server.extraction.schema import ExtractionResult, ExtractionTiming, ImageMeta


def extract_from_upload(
    image_path: Path,
    *,
    image_id: str | None = None,
    api_key: str | None = None,
    backend: str | None = None,
    exif: dict[str, Any] | None = None,
) -> ExtractionResult:
    """Extract products from a persisted image file via the configured backend."""
    stem = image_id or image_path.stem
    meta_exif = exif or {}
    meta = ImageMeta(
        image_id=stem,
        source_file=str(image_path),
        gps_latitude=meta_exif.get("GPSLatitude"),
        gps_longitude=meta_exif.get("GPSLongitude"),
        captured_at=meta_exif.get("captured_at"),
        date_folder=meta_exif.get("date_folder"),
    )
    products_result = extract_products_from_image(
        image_path,
        api_key=api_key,
        backend=backend,
    )
    return ExtractionResult(
        image_path=str(image_path),
        meta=meta,
        products=products_result.products,
        photo_type=products_result.photo_type,
        raw_response=products_result.raw_response,
        extractor=current_extractor_name(backend),
        timing=ExtractionTiming(
            llm_ms=products_result.llm_ms,
            other_ms=products_result.other_ms,
            model=products_result.model,
        ),
    )
