"""Oracle control: extract with known photo type (no classification)."""

from __future__ import annotations

from pathlib import Path

from experiment.approaches.types import ApproachRunResult
from experiment.dataset import PhotoType
from grocery_extract.cursor_extractor import extract_products_from_image


def run_oracle(
    image_path: Path,
    *,
    expected_type: PhotoType,
    backend: str,
    model: str,
    llm_scale_pct: int | None = None,
) -> ApproachRunResult:
    result = extract_products_from_image(
        image_path,
        backend=backend,
        model=model,
        prompt_variant=expected_type,
        llm_scale_pct=llm_scale_pct,
    )
    products = [p.to_product_dict() for p in result.products]
    return ApproachRunResult(
        predicted_type=expected_type,
        products=products,
        raw_response=result.raw_response,
        classify_ms=0,
        extract_ms=result.llm_ms,
        total_llm_ms=result.llm_ms,
        llm_calls=1,
    )
