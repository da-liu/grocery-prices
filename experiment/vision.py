"""Vision LLM wrapper for experiment approaches."""

from __future__ import annotations

import time
from pathlib import Path

from grocery_extract.cursor_extractor import (
    _run_cursor_sdk,
    _run_gemini_direct,
    configured_api_key,
    default_extract_model,
)

ROOT = Path(__file__).resolve().parents[1]


def run_vision(
    image_path: Path,
    *,
    prompt: str,
    backend: str,
    model: str,
    llm_scale_pct: int | None = None,
) -> tuple[str, int]:
    """Run a single vision LLM call. Returns (raw_response, elapsed_ms)."""
    _ = llm_scale_pct
    api_key = configured_api_key(None, backend)
    image_path = image_path.resolve()
    started = time.perf_counter()
    if backend == "gemini_direct":
        raw = _run_gemini_direct(image_path, prompt=prompt, api_key=api_key, model=model)
    else:
        raw = _run_cursor_sdk(
            image_path,
            prompt=prompt,
            api_key=api_key,
            model=model,
            cwd=ROOT,
        )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return raw, elapsed_ms


def default_model_for_backend(backend: str) -> str:
    return default_extract_model(backend)
