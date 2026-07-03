#!/usr/bin/env python3
"""Compare Cursor SDK image attachment modes: from_file vs url_image."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from cursor_sdk import Agent, AgentOptions, CloudAgentOptions, CloudRepository, CursorAgentError, SDKImage, UserMessage  # pyright: ignore[reportMissingImports]

ROOT = Path(__file__).resolve().parents[2]

CURSOR_API_KEY = "crsr_b0244092fdf0a518b5debbb8bf396d2dedcf8b133bd33c5a054378a524690b89"
LOCAL_IMAGE_PATH = ROOT / "viewer" / "public" / "sdk-image-tests" / "IMG_2044_scale_025.jpg"
PUBLIC_IMAGE_URL = "https://g.daliu.ca/sdk-image-tests/IMG_2044_scale_025.jpg"
REPO_URL = "https://github.com/da-liu/grocery-prices.git"
MODEL = "gemini-3-flash"

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
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model response")
    return json.loads(cleaned[start : end + 1])


def summarize_attachment(image: SDKImage) -> str:
    payload = image.to_json()
    if "data" in payload:
        data = payload["data"]
        base64_chars = len(str(data.get("data", "")))
        return (
            "wire=data "
            f"mime={data.get('mimeType', '')} "
            f"base64_chars={base64_chars}"
        )
    if "url" in payload:
        return f"wire=url url={payload['url'].get('url', '')}"
    return "wire=unknown"


def run_variant(label: str, image: SDKImage) -> tuple[dict, str, list[tuple[str, float]], str]:
    api_key = CURSOR_API_KEY.strip()
    if not api_key:
        raise RuntimeError("Set CURSOR_API_KEY near the top of this script")

    timings: list[tuple[str, float]] = []

    started = time.perf_counter()
    attachment_summary = summarize_attachment(image)
    timings.append((f"{label}.serialize_attachment", time.perf_counter() - started))

    started = time.perf_counter()
    try:
        result = Agent.prompt(
            UserMessage(text=PROMPT, images=[image]),
            AgentOptions(
                api_key=api_key,
                model=MODEL,
                cloud=CloudAgentOptions(
                    repos=[CloudRepository(url=REPO_URL)],
                    skip_reviewer_request=True,
                ),
            ),
        )
    except CursorAgentError as err:
        raise RuntimeError(f"{label} failed: {err.message}") from err
    timings.append((f"{label}.cursor.prompt", time.perf_counter() - started))

    if result.status == "error":
        raise RuntimeError(f"{label} run failed: {result.id}")

    raw = (result.result or "").strip()
    if not raw:
        raise RuntimeError(f"{label} returned an empty response")

    started = time.perf_counter()
    parsed = extract_json_object(raw)
    timings.append((f"{label}.parse_json", time.perf_counter() - started))
    return parsed, raw, timings, attachment_summary


def main() -> int:
    if not LOCAL_IMAGE_PATH.exists():
        print(f"Photo not found: {LOCAL_IMAGE_PATH}", file=sys.stderr)
        return 1

    print(f"local image: {LOCAL_IMAGE_PATH}")
    print(f"public url:  {PUBLIC_IMAGE_URL}")
    print(f"repo url:    {REPO_URL}")
    print(f"model: {MODEL} (Cursor SDK cloud)")
    print("prompt:", PROMPT.splitlines()[0], "...")
    print()

    started = time.perf_counter()
    from_file_image = SDKImage.from_file(str(LOCAL_IMAGE_PATH))
    from_file_build = time.perf_counter() - started

    started = time.perf_counter()
    url_image = SDKImage.url_image(PUBLIC_IMAGE_URL)
    url_image_build = time.perf_counter() - started

    from_file_parsed, from_file_raw, from_file_timings, from_file_summary = run_variant(
        "from_file",
        from_file_image,
    )
    from_file_timings.insert(0, ("from_file.build_image", from_file_build))

    url_parsed, url_raw, url_timings, url_summary = run_variant(
        "url_image",
        url_image,
    )
    url_timings.insert(0, ("url_image.build_image", url_image_build))

    print("from_file attachment:", from_file_summary)
    print("url_image attachment:", url_summary)
    print()

    print(f"from_file: {len(from_file_parsed.get('products', []))} products")
    print(format_timing_table(from_file_timings))
    print()
    print(from_file_raw)
    print()

    print(f"url_image: {len(url_parsed.get('products', []))} products")
    print(format_timing_table(url_timings))
    print()
    print(url_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
