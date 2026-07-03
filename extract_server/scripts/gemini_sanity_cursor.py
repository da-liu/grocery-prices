#!/usr/bin/env python3
"""One-shot sanity check: 1 photo -> Gemini 3 Flash via Cursor SDK."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions, SDKImage, UserMessage  # pyright: ignore[reportMissingImports]

ROOT = Path(__file__).resolve().parents[2]

CURSOR_API_KEY = "crsr_b0244092fdf0a518b5debbb8bf396d2dedcf8b133bd33c5a054378a524690b89"
IMAGE_PATH = ROOT / "data" / "test-data" / "IMG_2044.HEIC"
SCALE_PCT = 25
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


def run_cursor_sdk(image_path: Path, prompt: str, model: str) -> tuple[dict, str, list[tuple[str, float]]]:
    api_key = CURSOR_API_KEY.strip()
    if not api_key:
        raise RuntimeError("Set CURSOR_API_KEY near the top of this script")

    timings: list[tuple[str, float]] = []
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
    timings.append(("cursor.prompt", time.perf_counter() - started))

    if result.status == "error":
        raise RuntimeError(f"Cursor agent run failed: {result.id}")

    raw = (result.result or "").strip()
    if not raw:
        raise RuntimeError("Empty response from Cursor agent")

    started = time.perf_counter()
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
        print(f"model: {MODEL} (Cursor SDK)")
        print("prompt:", PROMPT.splitlines()[0], "...")
        print()

        parsed, raw, cursor_timings = run_cursor_sdk(image, PROMPT, MODEL)
        timings.extend(cursor_timings)
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
