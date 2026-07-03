#!/usr/bin/env python3
"""One-shot sanity check: 1 photo -> Qwen vision API, minimal prompt."""

from __future__ import annotations

import base64
import json
import mimetypes
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

API_KEY = "sk-ws-H.YLLPDM.83rm.MEYCIQCCUYMKnsUjwfp7RCjAdP8-7QRr016RQcDKDgFqXZsuOgIhAJSlM3gmPTMr8tadWsmRdFFLh9n8vIf7SPeFCsKG7DkN"
IMAGE_PATH = ROOT / "data" / "test-data" / "IMG_2044.HEIC"
SCALE_PCT = 25
MODEL = "qwen3.7-plus"
REGION = "ap-southeast-1"
WORKSPACE_ID = "ws-wdpux4dcyejddyd1"
API_HOST = f"{WORKSPACE_ID}.{REGION}.maas.aliyuncs.com"
OPENAI_COMPATIBLE_BASE_URL = f"https://{API_HOST}/compatible-mode/v1"
DASHSCOPE_BASE_URL = f"https://{API_HOST}/api/v1"
ENDPOINT = f"{OPENAI_COMPATIBLE_BASE_URL}/chat/completions"

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


def image_dimensions(path: Path) -> tuple[int, int]:
    width = subprocess.check_output(["sips", "-g", "pixelWidth", str(path)], text=True)
    height = subprocess.check_output(["sips", "-g", "pixelHeight", str(path)], text=True)
    return (
        int(width.strip().rsplit(":", 1)[-1].strip()),
        int(height.strip().rsplit(":", 1)[-1].strip()),
    )


def scale_image(source: Path, scale_pct: int, out_dir: Path) -> Path:
    width, height = image_dimensions(source)
    max_dim = max(1, round(max(width, height) * scale_pct / 100))
    dest = out_dir / f"{source.stem}_scale_{scale_pct:03d}.jpg"
    subprocess.run(
        ["sips", "-Z", str(max_dim), "-s", "format", "jpeg", str(source), "--out", str(dest)],
        check=True,
        capture_output=True,
    )
    return dest


def guess_mime_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type or "application/octet-stream"


def make_data_url(path: Path) -> str:
    mime_type = guess_mime_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


def run_qwen(image_path: Path, prompt: str, model: str) -> tuple[dict, str, list[tuple[str, float]]]:
    api_key = API_KEY.strip()
    if not api_key:
        raise RuntimeError("Set API_KEY near the top of this script")

    timings: list[tuple[str, float]] = []

    started = time.perf_counter()
    data_url = make_data_url(image_path)
    timings.append(("encode_image", time.perf_counter() - started))

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.1,
        "stream": False,
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
    source = IMAGE_PATH
    if not source.exists():
        print(f"Photo not found: {source}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        timings: list[tuple[str, float]] = []

        started = time.perf_counter()
        image = scale_image(source, SCALE_PCT, Path(tmp))
        timings.append(("scale_image", time.perf_counter() - started))
        print(f"image: {source.name} @ {SCALE_PCT}% -> {image.name} ({image.stat().st_size // 1024} KB)")
        print(f"model: {MODEL} (Qwen API)")
        print(f"endpoint host: {API_HOST}")
        print(f"openai base: {OPENAI_COMPATIBLE_BASE_URL}")
        print("prompt:", PROMPT.splitlines()[0], "...")
        print()

        parsed, raw, qwen_timings = run_qwen(image, PROMPT, MODEL)
        timings.extend(qwen_timings)
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
