"""Shared types for experiment approaches."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApproachRunResult:
    predicted_type: str
    products: list[dict]
    raw_response: str
    classify_ms: int
    extract_ms: int
    total_llm_ms: int
    llm_calls: int
