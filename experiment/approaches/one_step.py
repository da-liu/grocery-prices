"""1-step unified classify + extract approach."""

from __future__ import annotations

from pathlib import Path

from experiment.approaches.types import ApproachRunResult
from experiment.parse_unified import parse_unified_response
from experiment.prompts import build_unified_prompt
from experiment.vision import run_vision


def run_one_step(
    image_path: Path,
    *,
    backend: str,
    model: str,
    llm_scale_pct: int | None = None,
) -> ApproachRunResult:
    prompt = build_unified_prompt()
    raw, elapsed_ms = run_vision(
        image_path,
        prompt=prompt,
        backend=backend,
        model=model,
        llm_scale_pct=llm_scale_pct,
    )
    parsed = parse_unified_response(raw)
    return ApproachRunResult(
        predicted_type=parsed.photo_type,
        products=parsed.products,
        raw_response=raw,
        classify_ms=0,
        extract_ms=elapsed_ms,
        total_llm_ms=elapsed_ms,
        llm_calls=1,
    )
