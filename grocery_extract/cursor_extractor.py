from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import httpx
from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions, SDKImage, UserMessage

from grocery_extract.image_prep import LLM_MAX_DIM, llm_scale_percent, prepare_image_for_llm
from grocery_extract.parse_response import parse_products_json
from grocery_extract.prompt import build_prompt, build_receipt_prompt
from grocery_extract.schema import ExtractedProduct

ROOT = Path(__file__).resolve().parents[1]
CURSOR_BACKEND = "cursor"
GEMINI_DIRECT_BACKEND = "gemini_direct"
DEFAULT_CURSOR_MODEL = "auto"
DEFAULT_GEMINI_DIRECT_MODEL = "gemini-3.1-flash-lite"


class CursorExtractError(RuntimeError):
    pass


def current_extract_backend() -> str:
    backend = os.environ.get("GROCERY_EXTRACT_BACKEND", CURSOR_BACKEND).strip().lower()
    if backend not in {CURSOR_BACKEND, GEMINI_DIRECT_BACKEND}:
        raise CursorExtractError(
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
            raise CursorExtractError("GEMINI_API_KEY or GOOGLE_API_KEY is required for direct Gemini extraction")
        return key
    key = os.environ.get("CURSOR_API_KEY")
    if not key:
        raise CursorExtractError("CURSOR_API_KEY is required for Cursor SDK extraction")
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
        raise CursorExtractError(f"Cursor agent startup failed: {err.message}") from err

    if result.status == "error":
        raise CursorExtractError(f"Cursor agent run failed: {result.id}")
    raw = result.result or ""
    if not raw.strip():
        raise CursorExtractError("Empty response from Cursor agent")
    return raw


def _run_gemini_direct(
    image_path: Path,
    *,
    prompt: str,
    api_key: str,
    model: str,
) -> str:
    image_bytes = image_path.read_bytes()
    mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
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
            raise CursorExtractError(f"Gemini API {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
    try:
        raw = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as err:
        raise CursorExtractError(f"Unexpected Gemini response shape: {json.dumps(body)[:500]}") from err
    if not raw.strip():
        raise CursorExtractError("Empty response from Gemini API")
    return raw


def extract_products_from_image(
    image_path: Path,
    *,
    api_key: str | None = None,
    model: str | None = None,
    backend: str | None = None,
    cwd: Path | None = None,
    prompt_variant: str = "shelf",
    llm_max_dim: int | None = None,
    llm_scale_pct: int | None = None,
) -> tuple[list[ExtractedProduct], str]:
    """Extract products from a grocery photo using the configured vision backend."""
    backend = backend or current_extract_backend()
    model = model or default_extract_model(backend)
    api_key = configured_api_key(api_key, backend)
    image_path = image_path.resolve()
    if not image_path.exists():
        raise CursorExtractError(f"Image not found: {image_path}")

    llm_path = prepare_image_for_llm(
        image_path,
        scale_pct=llm_scale_pct if llm_scale_pct is not None else (None if llm_max_dim is not None else llm_scale_percent()),
        max_dim=llm_max_dim if llm_max_dim is not None else LLM_MAX_DIM,
    )
    cleanup_llm_path = llm_path != image_path

    cwd = cwd or ROOT
    prompt = build_receipt_prompt() if prompt_variant == "receipt" else build_prompt()

    try:
        if backend == GEMINI_DIRECT_BACKEND:
            raw = _run_gemini_direct(llm_path, prompt=prompt, api_key=api_key, model=model)
        else:
            raw = _run_cursor_sdk(llm_path, prompt=prompt, api_key=api_key, model=model, cwd=cwd)
    finally:
        if cleanup_llm_path:
            llm_path.unlink(missing_ok=True)

    products = parse_products_json(raw)
    return products, raw
