#!/usr/bin/env python3
"""Step-by-step benchmark of photo upload and extraction pipeline."""

from __future__ import annotations

import argparse
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract_server"))


@dataclass
class StepTimer:
    steps: list[tuple[str, float]] = field(default_factory=list)
    _stack: list[tuple[str, float]] = field(default_factory=list)

    @contextmanager
    def measure(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self.steps.append((name, elapsed))

    def add(self, name: str, elapsed: float) -> None:
        self.steps.append((name, elapsed))

    def report(self, title: str) -> None:
        total = sum(elapsed for _, elapsed in self.steps)
        print(f"\n{title}")
        print("-" * len(title))
        ranked = sorted(self.steps, key=lambda item: item[1], reverse=True)
        for name, elapsed in ranked:
            pct = (elapsed / total * 100) if total else 0
            print(f"  {elapsed:7.3f}s  ({pct:5.1f}%)  {name}")
        print(f"  {'-' * 40}")
        print(f"  {total:7.3f}s  (100.0%)  total")


def run_direct_benchmark(image_path: Path, timer: StepTimer) -> dict:
    import tempfile

    from extract_server.users_db import init_db, register_user
    from grocery_extract.duplicate import file_content_hash
    from grocery_extract.extract_worker import ExtractionJob
    from grocery_extract.ingest import (
        _persist_image,
        _today_folder,
        accept_upload,
        run_extraction,
    )
    from grocery_extract.user_stores_db import list_user_stores_as_dicts
    from grocery_extract.catalog_db import (
        find_photo_by_content_hash,
        list_products_for_matching,
        save_photo_pending,
        set_extraction_status,
    )
    from grocery_extract.cursor_extractor import extract_products_from_image
    from grocery_extract.catalog_db import finalize_photo_extraction
    from grocery_extract.parse_response import parse_products_json
    from grocery_extract.pipeline import extract_from_upload
    from grocery_extract.photo_stores import image_needs_store_label
    from grocery_extract.product_matching import overlapping_product_keys, products_to_match_rows
    from grocery_extract.stores import store_from_gps
    from grocery_extract.exif import captured_at_from_exif, date_folder_from_exif

    init_db()
    user = register_user(f"bench_{int(time.time())}", "password12345")
    user_id = user.id

    with timer.measure("1. read_upload_bytes"):
        upload_bytes = image_path.read_bytes()

    with tempfile.TemporaryDirectory(prefix="grocery-bench-") as tmp:
        upload_path = Path(tmp) / image_path.name
        with timer.measure("2. write_temp_file"):
            upload_path.write_bytes(upload_bytes)

        with timer.measure("3. sha256_content_hash"):
            content_hash = file_content_hash(upload_path)

        with timer.measure("4. db_duplicate_lookup"):
            duplicate_of = find_photo_by_content_hash(user_id, content_hash)

        with timer.measure("5. client_metadata"):
            exif: dict = {}

        raw_dt = exif.get("DateTimeOriginal")
        date_folder = date_folder_from_exif(raw_dt) or _today_folder()
        captured_at = captured_at_from_exif(raw_dt)
        image_id = "IMG_9999"

        with timer.measure("6. persist_image_to_disk"):
            original_key, photo_key, _suffix = _persist_image(
                upload_path, image_id, date_folder, user_id
            )

        with timer.measure("7. db_list_user_stores"):
            user_stores = list_user_stores_as_dicts(user_id)

        with timer.measure("8. gps_store_match"):
            store_location_id = None
            lat = exif.get("GPSLatitude")
            lon = exif.get("GPSLongitude")
            if lat is not None and lon is not None:
                matched = store_from_gps(lat, lon, user_stores)
                if matched:
                    store_location_id = matched["id"]

        with timer.measure("9. db_save_photo_pending"):
            save_photo_pending(
                user_id,
                photo_id=image_id,
                photo_type="shelf",
                original_blob_key=original_key,
                photo_blob_key=photo_key,
                content_hash=content_hash,
                gps_latitude=lat,
                gps_longitude=lon,
                captured_at=captured_at,
                store_location_id=store_location_id,
            )

        jpg_path = upload_path  # after persist, use real path
        from grocery_extract.user_paths import user_photos_dir

        jpg_path = user_photos_dir(user_id, date_folder) / "jpg" / f"{image_id}.jpg"

        with timer.measure("10. db_set_status_processing"):
            set_extraction_status(user_id, image_id, "processing")

        with timer.measure("11. llm_extract"):
            llm_path = jpg_path

        with timer.measure("12. cursor_sdk_agent_prompt (LLM)"):
            products, raw = extract_products_from_image(jpg_path, prompt_variant="shelf")

        with timer.measure("13. parse_products_json"):
            _ = parse_products_json(raw)

        product_dicts = [product.to_product_dict() for product in products]

        with timer.measure("14. db_finalize_photo_extraction"):
            product_count = finalize_photo_extraction(
                user_id,
                image_id,
                extractor="cursor_sdk",
                raw_response=raw,
                products=product_dicts,
            )

        with timer.measure("15. db_list_products_for_matching"):
            existing_products = list_products_for_matching(user_id)

        with timer.measure("16. overlap_detection"):
            location = {"store": "Unknown store", "latitude": lat, "longitude": lon}
            new_rows = products_to_match_rows(
                product_dicts,
                image_id=image_id,
                location=location,
                captured_at=captured_at,
            )
            overlaps = overlapping_product_keys(new_rows, existing_products)

        return {
            "image_id": image_id,
            "product_count": product_count,
            "duplicate_of": duplicate_of,
            "overlaps": len(overlaps),
        }


def run_http_benchmark(image_path: Path, timer: StepTimer) -> dict:
    from fastapi.testclient import TestClient
    from server import app

    client = TestClient(app)
    with timer.measure("H1. register_user"):
        reg = client.post(
            "/api/auth/register",
            json={"username": f"http_bench_{int(time.time())}", "password": "password12345"},
        )
        reg.raise_for_status()
        headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    upload_bytes = image_path.read_bytes()
    with timer.measure("H2. POST /api/photos/bulk (accept)"):
        upload = client.post(
            "/api/photos/bulk",
            headers=headers,
            files=[("files", (image_path.name, upload_bytes, "image/jpeg"))],
            data={"source": "upload"},
        )
    upload.raise_for_status()
    image_id = upload.json()["results"][0]["image_id"]

    poll_start = time.perf_counter()
    polls = 0
    final: dict = {}
    deadline = time.perf_counter() + 300
    while time.perf_counter() < deadline:
        polls += 1
        resp = client.post("/api/photos/status", headers=headers, json={"ids": [image_id]})
        resp.raise_for_status()
        final = resp.json()["results"][0]
        if final.get("extraction_status") in {"done", "failed"}:
            break
        time.sleep(1.5)
    timer.add("H3. poll_until_done (incl. background LLM)", time.perf_counter() - poll_start)
    timer.add(f"    poll_requests ({polls} calls)", 0.0)  # metadata row

    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        type=Path,
        default=ROOT / "data" / "test-data" / "IMG_0003.jpg",
    )
    args = parser.parse_args()

    if not os.environ.get("CURSOR_API_KEY"):
        print("CURSOR_API_KEY required", file=sys.stderr)
        return 1
    if not args.image.exists():
        print(f"Image not found: {args.image}", file=sys.stderr)
        return 1

    size_kb = args.image.stat().st_size / 1024
    print(f"Sample image: {args.image}")
    print(f"File size: {size_kb:.1f} KB")

    direct_timer = StepTimer()
    print("\nRunning direct pipeline benchmark (instrumented steps)...")
    direct_result = run_direct_benchmark(args.image, direct_timer)
    direct_timer.report("Direct pipeline breakdown")

    http_timer = StepTimer()
    print("\nRunning HTTP frontend-flow benchmark...")
    http_result = run_http_benchmark(args.image, http_timer)
    http_timer.report("HTTP frontend-flow breakdown")

    print("\nResults")
    print("-------")
    print(f"Direct extraction products: {direct_result.get('product_count')}")
    print(f"HTTP extraction status: {http_result.get('extraction_status')}")
    print(f"HTTP product count: {http_result.get('product_count')}")

    direct_total = sum(e for _, e in direct_timer.steps)
    http_accept = next((e for n, e in http_timer.steps if "bulk" in n), 0)
    http_poll = next((e for n, e in http_timer.steps if "poll_until_done" in n), 0)
    llm_time = next((e for n, e in direct_timer.steps if "LLM" in n), 0)

    print("\nKey takeaways")
    print("-------------")
    print(f"  Fast accept path (HTTP):     {http_accept:.3f}s")
    print(f"  Background extraction wait:  {http_poll:.3f}s")
    print(f"  LLM alone (direct measure):  {llm_time:.3f}s  ({llm_time/direct_total*100:.0f}% of pipeline)")
    print(f"  All non-LLM steps combined:  {direct_total - llm_time:.3f}s")

    if http_result.get("extraction_status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
