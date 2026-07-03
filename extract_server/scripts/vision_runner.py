"""Vision LLM runners for experiments (Cursor SDK and direct Gemini API)."""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import httpx

from grocery_extract.parse_response import parse_products_json

ROOT = Path(__file__).resolve().parents[2]

# Google API model IDs may differ slightly from Cursor SDK slugs.
GEMINI_API_MODEL_MAP = {
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-3-flash": "gemini-3-flash-preview",
}


def run_cursor_vision(
    image_path: Path,
    *,
    prompt: str,
    model: str,
    api_key: str | None = None,
) -> tuple[list[dict], str, float]:
    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions, SDKImage, UserMessage

    api_key = api_key or os.environ.get("CURSOR_API_KEY")
    if not api_key:
        raise RuntimeError("CURSOR_API_KEY is required")

    started = time.perf_counter()
    try:
        result = Agent.prompt(
            UserMessage(text=prompt, images=[SDKImage.from_file(str(image_path))]),
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=str(ROOT)),
            ),
        )
    except CursorAgentError as err:
        raise RuntimeError(f"Cursor agent failed: {err.message}") from err

    elapsed = time.perf_counter() - started
    if result.status == "error":
        raise RuntimeError(f"Cursor agent run failed: {result.id}")

    raw = result.result or ""
    if not raw.strip():
        raise RuntimeError("Empty response from Cursor agent")

    products = [p.to_product_dict() for p in parse_products_json(raw)]
    return products, raw, elapsed


def run_gemini_direct(
    image_path: Path,
    *,
    prompt: str,
    model: str,
    api_key: str | None = None,
) -> tuple[list[dict], str, float]:
    api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required for direct Gemini API")

    api_model = GEMINI_API_MODEL_MAP.get(model, model)
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent"
    started = time.perf_counter()
    with httpx.Client(timeout=300.0) as client:
        resp = client.post(url, params={"key": api_key}, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
    elapsed = time.perf_counter() - started

    try:
        raw = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as err:
        raise RuntimeError(f"Unexpected Gemini response shape: {json.dumps(body)[:500]}") from err

    products = [p.to_product_dict() for p in parse_products_json(raw)]
    return products, raw, elapsed
