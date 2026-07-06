from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from grocery_extract.cursor_extractor import (
    CursorExtractError,
    _run_cursor_sdk,
    _run_gemini_direct,
    configured_api_key,
    current_extract_backend,
    default_extract_model,
)

ROOT = Path(__file__).resolve().parents[1]

CLASSIFY_PROMPT = """Classify this grocery image.
Return JSON only: {"type":"receipt"} if it is a printed grocery receipt with line items, otherwise {"type":"shelf"}."""


@dataclass(frozen=True)
class PhotoClassification:
    photo_type: str
    classify_ms: int


def classify_photo_type(
    image_path: Path,
    *,
    api_key: str | None = None,
) -> PhotoClassification:
    backend = current_extract_backend()
    model = default_extract_model(backend)
    api_key = configured_api_key(api_key, backend)
    image_path = image_path.resolve()
    if not image_path.exists():
        raise CursorExtractError(f"Image not found: {image_path}")

    start = time.perf_counter()
    if backend == "gemini_direct":
        raw = _run_gemini_direct(image_path, prompt=CLASSIFY_PROMPT, api_key=api_key, model=model)
    else:
        raw = _run_cursor_sdk(
            image_path,
            prompt=CLASSIFY_PROMPT,
            api_key=api_key,
            model=model,
            cwd=ROOT,
        )

    classify_ms = int((time.perf_counter() - start) * 1000)
    photo_type = _parse_classification(raw)
    return PhotoClassification(photo_type=photo_type, classify_ms=classify_ms)


def _parse_classification(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        lowered = text.lower()
        if "receipt" in lowered:
            return "receipt"
        return "shelf"
    value = str(payload.get("type", "shelf")).strip().lower()
    return "receipt" if value == "receipt" else "shelf"
