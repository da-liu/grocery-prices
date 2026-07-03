#!/usr/bin/env python3
"""One-shot sanity check: 1 photo -> GLM vision API, minimal prompt."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

API_KEY = "fb1c88080ff14684b71fb7449e689f54.9QdXwtvjQLx01CO0"
PUBLIC_IMAGE_PATH = ROOT / "viewer" / "public" / "sdk-image-tests" / "IMG_2044_scale_025.jpg"
PUBLIC_IMAGE_URL = "https://g.daliu.ca/sdk-image-tests/IMG_2044_scale_025.jpg"
MODEL = "glm-4.6v-flash"
ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"

PROMPT = """List every grocery product with a visible price tag in this photo.
Return JSON only: {"products":[{"product_name":"...","price":0.0}]}"""


def format_timing_table(timings: list[tuple[str, float]]) -> str:
    rows = timings + [("total", sum(seconds for _, seconds in timings))]
    step_width = max(len("step"), *(len(step) for step, _ in rows))
    seconds_width = max(len("seconds"), *(len(f"{seconds:.3f}") for _, seconds in rows))
    lines = [
        f"{'step':<{step_width}}  {'seconds':>{seconds_width}}",
        f"{'-' * step_width}  {'-' * seconds_width}",
    ]
    for step, seconds in rows:
        lines.append(f"{step:<{step_width}}  {seconds:>{seconds_width}.3f}")
    return "\n".join(lines)


def extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model response")
    return json.loads(cleaned[start : end + 1])


def extract_message_text(body: dict) -> str:
    content = body["choices"][0]["message"]["content"]
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    raise RuntimeError(f"Unexpected response content shape: {json.dumps(body)[:500]}")


def run_glm(image_url: str, prompt: str, model: str) -> tuple[dict, str, list[tuple[str, float]]]:
    api_key = API_KEY.strip()
    if not api_key:
        raise RuntimeError("Set API_KEY near the top of this script")

    timings: list[tuple[str, float]] = []

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "thinking": {"type": "enabled"},
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    timings.append(("generate", time.perf_counter() - started))

    started = time.perf_counter()
    raw = extract_message_text(body)
    parsed = extract_json_object(raw)
    timings.append(("parse_json", time.perf_counter() - started))
    return parsed, raw, timings


def main() -> int:
    if not PUBLIC_IMAGE_PATH.exists():
        print(f"Photo not found: {PUBLIC_IMAGE_PATH}", file=sys.stderr)
        return 1

    timings: list[tuple[str, float]] = []
    print(f"image path: {PUBLIC_IMAGE_PATH}")
    print(f"image url:  {PUBLIC_IMAGE_URL}")
    print(f"model: {MODEL} (GLM API)")
    print("prompt:", PROMPT.splitlines()[0], "...")
    print()

    parsed, raw, glm_timings = run_glm(PUBLIC_IMAGE_URL, PROMPT, MODEL)
    timings.extend(glm_timings)
    products = parsed.get("products", [])
    total_seconds = sum(seconds for _, seconds in timings)

    print(f"done in {total_seconds:.1f}s, {len(products)} products")
    print()
    print(format_timing_table(timings))
    print()
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
