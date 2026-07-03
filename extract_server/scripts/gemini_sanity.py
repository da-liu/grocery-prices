#!/usr/bin/env python3
"""One-shot sanity check: 1 photo -> Gemini 3 Flash (direct API), minimal prompt."""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGE_PATH = ROOT / "data" / "test-data" / "IMG_2044.HEIC"
SCALE_PCT = 25
MODEL = "gemini-3-flash"

# Google API model IDs may differ slightly from Cursor SDK slugs.
GEMINI_API_MODEL_MAP = {
    "gemini-3-flash": "gemini-3-flash-preview",
}

PROMPT = """List every grocery product with a visible price tag in this photo.
Return JSON only: {"products":[{"product_name":"...","price":0.0}]}"""


def configured_api_key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()


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


def upload_gemini_file(path: Path, api_key: str) -> tuple[str, str, list[tuple[str, float]]]:
    timings: list[tuple[str, float]] = []
    mime_type = guess_mime_type(path)
    start_url = (
        "https://generativelanguage.googleapis.com/upload/v1beta/files?"
        + urllib.parse.urlencode({"key": api_key})
    )
    metadata = {"file": {"display_name": path.name}}
    start_request = urllib.request.Request(
        start_url,
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(path.stat().st_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
        },
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(start_request, timeout=300) as response:
        upload_url = response.headers.get("X-Goog-Upload-URL")
    timings.append(("files.start", time.perf_counter() - started))
    if not upload_url:
        raise RuntimeError("Gemini Files API did not return an upload URL")

    upload_request = urllib.request.Request(
        upload_url,
        data=path.read_bytes(),
        headers={
            "Content-Length": str(path.stat().st_size),
            "Content-Type": mime_type,
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(upload_request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    timings.append(("files.upload", time.perf_counter() - started))

    file_info = body.get("file") or {}
    file_uri = file_info.get("uri")
    if not file_uri:
        raise RuntimeError(f"Gemini Files API response missing file URI: {json.dumps(body)[:500]}")
    return file_uri, file_info.get("mimeType") or mime_type, timings


def run_gemini(image_path: Path, prompt: str, model: str) -> tuple[dict, str, list[tuple[str, float]]]:
    api_key = configured_api_key()
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment")

    api_model = GEMINI_API_MODEL_MAP.get(model, model)
    file_uri, mime_type, timings = upload_gemini_file(image_path, api_key)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "file_data": {
                            "mime_type": mime_type,
                            "file_uri": file_uri,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{api_model}:generateContent?"
        + urllib.parse.urlencode({"key": api_key})
    )
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.loads(response.read().decode("utf-8"))
    timings.append(("generate", time.perf_counter() - started))

    started = time.perf_counter()
    raw = body["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(raw)
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
        print(f"model: {MODEL} (direct API)")
        print("prompt:", PROMPT.splitlines()[0], "...")
        print()

        parsed, raw, gemini_timings = run_gemini(image, PROMPT, MODEL)
        timings.extend(gemini_timings)
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
