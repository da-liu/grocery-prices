#!/usr/bin/env python3
"""Benchmark upload accept time vs full extraction time (frontend-style flow)."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract_server"))

from fastapi.testclient import TestClient


def poll_until_done(client: TestClient, headers: dict, image_id: str, timeout_s: float = 300.0) -> dict:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        resp = client.post("/api/photos/status", headers=headers, json={"ids": [image_id]})
        resp.raise_for_status()
        result = resp.json()["results"][0]
        status = result.get("extraction_status")
        if status in {"done", "failed"}:
            return result
        time.sleep(1.5)
    raise TimeoutError(f"Extraction for {image_id} did not finish within {timeout_s}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark grocery photo upload flow")
    parser.add_argument(
        "--image",
        type=Path,
        help="JPEG path to upload (defaults to first benchmark fixture)",
    )
    args = parser.parse_args()

    if not os.environ.get("CURSOR_API_KEY"):
        print("CURSOR_API_KEY is required for live extraction benchmark", file=sys.stderr)
        return 1

    image_path = args.image
    if image_path is None:
        fixtures = sorted((ROOT / "extract_server" / "tests" / "fixtures").glob("**/*.jpg"))
        if not fixtures:
            print("No fixture image found; pass --image", file=sys.stderr)
            return 1
        image_path = fixtures[0]

    if not image_path.exists():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 1

    from server import app

    client = TestClient(app)
    username = f"bench_{int(time.time())}"
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password12345"},
    )
    reg.raise_for_status()
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    t0 = time.perf_counter()
    upload = client.post(
        "/api/photos/bulk",
        headers=headers,
        files=[("files", (image_path.name, image_path.read_bytes(), "image/jpeg"))],
        data={"source": "upload"},
    )
    accept_s = time.perf_counter() - t0
    upload.raise_for_status()
    assert upload.status_code == 202, upload.text
    image_id = upload.json()["results"][0]["image_id"]

    t1 = time.perf_counter()
    final = poll_until_done(client, headers, image_id)
    total_s = time.perf_counter() - t0
    extraction_s = time.perf_counter() - t1

    print(f"image: {image_path}")
    print(f"image_id: {image_id}")
    print(f"accept_response_s: {accept_s:.2f}")
    print(f"poll_to_done_s: {extraction_s:.2f}")
    print(f"frontend_total_s: {total_s:.2f}")
    print(f"extraction_status: {final.get('extraction_status')}")
    print(f"product_count: {final.get('product_count')}")
    if final.get("extraction_error"):
        print(f"extraction_error: {final['extraction_error']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
