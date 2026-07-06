"""Production-mirror 2-step approach: classify then extract."""

from __future__ import annotations

import json
from pathlib import Path

from experiment.approaches.types import ApproachRunResult
from experiment.vision import run_vision
from grocery_extract.cursor_extractor import extract_products_from_image
from grocery_extract.photo_classifier import CLASSIFY_PROMPT, _parse_classification


def run_two_step(
    image_path: Path,
    *,
    backend: str,
    model: str,
    llm_scale_pct: int | None = None,
) -> ApproachRunResult:
    classify_raw, classify_ms = run_vision(
        image_path,
        prompt=CLASSIFY_PROMPT,
        backend=backend,
        model=model,
        llm_scale_pct=llm_scale_pct,
    )
    photo_type = _parse_classification(classify_raw)

    result = extract_products_from_image(
        image_path,
        backend=backend,
        model=model,
        prompt_variant=photo_type,
        llm_scale_pct=llm_scale_pct,
    )
    products = [p.to_product_dict() for p in result.products]
    raw_response = json.dumps(
        {
            "classification_raw": classify_raw,
            "classification_type": photo_type,
            "classify_ms": classify_ms,
            "extract_raw": result.raw_response,
        },
        ensure_ascii=False,
    )
    return ApproachRunResult(
        predicted_type=photo_type,
        products=products,
        raw_response=raw_response,
        classify_ms=classify_ms,
        extract_ms=result.llm_ms,
        total_llm_ms=classify_ms + result.llm_ms,
        llm_calls=2,
    )
