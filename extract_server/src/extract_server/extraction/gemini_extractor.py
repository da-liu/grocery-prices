from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from extract_server.core.exceptions import ConfigError, ExtractionError
from extract_server.extraction.parse_response import parse_unified_response
from extract_server.extraction.prompt import build_unified_prompt
from extract_server.extraction.schema import ExtractedProduct

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
EXTRACTOR_NAME = "gemini_direct"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractImageResult:
    products: list[ExtractedProduct]
    photo_type: str
    raw_response: str
    llm_ms: int
    other_ms: int
    model: str


def default_extract_model() -> str:
    return DEFAULT_GEMINI_MODEL


def current_extractor_name() -> str:
    return EXTRACTOR_NAME


def configured_api_key(api_key: str | None = None) -> str:
    if api_key:
        return api_key
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ConfigError("GEMINI_API_KEY is required for Gemini extraction")
    return key


def _run_gemini(
    image_path: Path,
    *,
    prompt: str,
    api_key: str,
    model: str,
) -> str:
    image_bytes = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    else:
        mime = "image/png"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(url, params={"key": api_key}, json=payload)
        if resp.status_code >= 400:
            logger.error(
                "gemini_api_error model=%s status=%s body_preview=%s",
                model,
                resp.status_code,
                resp.text[:200],
            )
            raise ExtractionError(f"Gemini API {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
    try:
        raw = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as err:
        logger.error("gemini_response_shape_error model=%s body_preview=%s", model, json.dumps(body)[:200])
        raise ExtractionError(f"Unexpected Gemini response shape: {json.dumps(body)[:500]}") from err
    if not raw.strip():
        raise ExtractionError("Empty response from Gemini API")
    return raw


def extract_products_from_image(
    image_path: Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> ExtractImageResult:
    """Classify and extract products from a grocery photo in one LLM call."""
    model = model or default_extract_model()
    api_key = configured_api_key(api_key)
    image_path = image_path.resolve()
    if not image_path.exists():
        raise ExtractionError(f"Image not found: {image_path}")

    call_start = time.perf_counter()
    prompt = build_unified_prompt()

    llm_start = time.perf_counter()
    raw = _run_gemini(image_path, prompt=prompt, api_key=api_key, model=model)
    llm_ms = int((time.perf_counter() - llm_start) * 1000)

    parsed = parse_unified_response(raw)
    other_ms = max(0, int((time.perf_counter() - call_start) * 1000) - llm_ms)
    logger.info(
        "llm_extract_complete model=%s llm_ms=%s other_ms=%s photo_type=%s products=%s",
        model,
        llm_ms,
        other_ms,
        parsed.photo_type,
        len(parsed.products),
    )
    return ExtractImageResult(
        products=parsed.products,
        photo_type=parsed.photo_type,
        raw_response=raw,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
    )
