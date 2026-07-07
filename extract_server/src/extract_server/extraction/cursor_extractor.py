from __future__ import annotations

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions, SDKImage, UserMessage

from extract_server.core.exceptions import ConfigError, CursorExtractError, ExtractionError
from extract_server.extraction.parse_response import parse_unified_response
from extract_server.extraction.prompt import build_unified_prompt
from extract_server.extraction.schema import ExtractedProduct

ROOT = Path(__file__).resolve().parents[1]
CURSOR_BACKEND = "cursor"
GEMINI_DIRECT_BACKEND = "gemini_direct"
VALID_EXTRACT_BACKENDS = frozenset({CURSOR_BACKEND, GEMINI_DIRECT_BACKEND})
DEFAULT_CURSOR_MODEL = "auto"
DEFAULT_GEMINI_DIRECT_MODEL = "gemini-3.1-flash-lite"

logger = logging.getLogger(__name__)


def normalize_extract_backend(backend: str) -> str:
    normalized = backend.strip().lower()
    if normalized not in VALID_EXTRACT_BACKENDS:
        raise ValueError(
            f"Unsupported extract backend: {backend}. "
            f"Expected {CURSOR_BACKEND} or {GEMINI_DIRECT_BACKEND}."
        )
    return normalized


@dataclass(frozen=True)
class ExtractImageResult:
    products: list[ExtractedProduct]
    photo_type: str
    raw_response: str
    llm_ms: int
    other_ms: int
    model: str


def current_extract_backend() -> str:
    backend = os.environ.get("GROCERY_EXTRACT_BACKEND", GEMINI_DIRECT_BACKEND).strip().lower()
    if backend not in VALID_EXTRACT_BACKENDS:
        raise ConfigError(
            f"Unsupported GROCERY_EXTRACT_BACKEND: {backend}. "
            f"Expected {CURSOR_BACKEND} or {GEMINI_DIRECT_BACKEND}."
        )
    return backend


def default_extract_model(backend: str | None = None) -> str:
    backend = backend or current_extract_backend()
    if backend == GEMINI_DIRECT_BACKEND:
        return DEFAULT_GEMINI_DIRECT_MODEL
    return DEFAULT_CURSOR_MODEL


def current_extractor_name(backend: str | None = None) -> str:
    return "gemini_direct" if (backend or current_extract_backend()) == GEMINI_DIRECT_BACKEND else "cursor_sdk"


def configured_api_key(api_key: str | None = None, backend: str | None = None) -> str:
    if api_key:
        return api_key
    backend = backend or current_extract_backend()
    if backend == GEMINI_DIRECT_BACKEND:
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ConfigError("GEMINI_API_KEY or GOOGLE_API_KEY is required for direct Gemini extraction")
        return key
    key = os.environ.get("CURSOR_API_KEY")
    if not key:
        raise ConfigError("CURSOR_API_KEY is required for Cursor SDK extraction")
    return key


def _run_cursor_sdk(
    image_path: Path,
    *,
    prompt: str,
    api_key: str,
    model: str,
    cwd: Path,
) -> str:
    try:
        result = Agent.prompt(
            UserMessage(
                text=prompt,
                images=[SDKImage.from_file(str(image_path))],
            ),
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=str(cwd)),
            ),
        )
    except CursorAgentError as err:
        logger.error("cursor_agent_startup_failed model=%s error=%s", model, err.message)
        raise ExtractionError(f"Cursor agent startup failed: {err.message}") from err

    if result.status == "error":
        logger.error("cursor_agent_run_failed model=%s run_id=%s", model, result.id)
        raise ExtractionError(f"Cursor agent run failed: {result.id}")
    raw = result.result or ""
    if not raw.strip():
        raise ExtractionError("Empty response from Cursor agent")
    return raw


def _run_gemini_direct(
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


def _run_vision_backend(
    image_path: Path,
    *,
    prompt: str,
    api_key: str,
    model: str,
    backend: str,
    cwd: Path,
) -> str:
    if backend == GEMINI_DIRECT_BACKEND:
        return _run_gemini_direct(image_path, prompt=prompt, api_key=api_key, model=model)
    return _run_cursor_sdk(image_path, prompt=prompt, api_key=api_key, model=model, cwd=cwd)


def extract_products_from_image(
    image_path: Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    cwd: Path | None = None,
) -> ExtractImageResult:
    """Classify and extract products from a grocery photo in one LLM call."""
    backend = backend or current_extract_backend()
    model = model or default_extract_model(backend)
    api_key = configured_api_key(api_key, backend)
    image_path = image_path.resolve()
    if not image_path.exists():
        raise ExtractionError(f"Image not found: {image_path}")

    call_start = time.perf_counter()

    cwd = cwd or ROOT
    prompt = build_unified_prompt()

    llm_start = time.perf_counter()
    raw = _run_vision_backend(
        image_path,
        prompt=prompt,
        api_key=api_key,
        model=model,
        backend=backend,
        cwd=cwd,
    )
    llm_ms = int((time.perf_counter() - llm_start) * 1000)

    parsed = parse_unified_response(raw)
    other_ms = max(0, int((time.perf_counter() - call_start) * 1000) - llm_ms)
    logger.info(
        "llm_extract_complete backend=%s model=%s llm_ms=%s other_ms=%s photo_type=%s products=%s",
        backend,
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
