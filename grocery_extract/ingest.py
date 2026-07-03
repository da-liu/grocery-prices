from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from grocery_extract.delete import delete_photo
from grocery_extract.duplicate import file_content_hash, find_exact_duplicate, set_content_hash
from grocery_extract.exif import (
    captured_at_from_exif,
    convert_heic_to_jpg,
    date_folder_from_exif,
    extract_exif,
    tool_path,
)
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.photo_stores import auto_assign_store_from_gps
from grocery_extract.product_matching import overlapping_product_keys
from grocery_extract.products_builder import build_product_lines, write_user_products_jsonl
from grocery_extract.schema import ExtractionResult
from grocery_extract.user_paths import (
    user_extractions_dir,
    user_meta_path,
    user_photos_dir,
    user_root,
)

ROOT = Path(__file__).resolve().parents[1]
TORONTO = ZoneInfo("America/Toronto")
DEFAULT_UPLOAD_WORKERS = int(os.environ.get("GROCERY_UPLOAD_WORKERS", "4"))


def _today_folder() -> str:
    return datetime.now(TORONTO).strftime("%Y_%m_%d")


def _max_image_num(user_id: str) -> int:
    max_num = 0
    photos_root = user_root(user_id) / "photos"
    if photos_root.exists():
        for path in photos_root.rglob("IMG_*.*"):
            stem = path.stem
            if stem.startswith("IMG_") and stem[4:].isdigit():
                max_num = max(max_num, int(stem[4:]))
    extractions = user_extractions_dir(user_id)
    if extractions.exists():
        for path in extractions.glob("IMG_*.json"):
            stem = path.stem
            if stem[4:].isdigit():
                max_num = max(max_num, int(stem[4:]))
    return max_num


def next_image_id(user_id: str) -> str:
    return f"IMG_{_max_image_num(user_id) + 1:04d}"


def allocate_image_ids(user_id: str, count: int) -> list[str]:
    """Reserve a contiguous block of image IDs before parallel ingest."""
    if count <= 0:
        return []
    start = _max_image_num(user_id) + 1
    return [f"IMG_{start + index:04d}" for index in range(count)]


def _load_meta_rows(user_id: str) -> list[dict]:
    path = user_meta_path(user_id)
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def _save_meta_rows(user_id: str, rows: list[dict]) -> None:
    path = user_meta_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")


def _upsert_meta(
    user_id: str,
    image_id: str,
    source_file: str,
    exif: dict,
    *,
    content_hash: str | None = None,
) -> None:
    rows = _load_meta_rows(user_id)
    row = {
        "SourceFile": source_file,
        "GPSLatitude": exif.get("GPSLatitude"),
        "GPSLongitude": exif.get("GPSLongitude"),
        "DateTimeOriginal": exif.get("DateTimeOriginal"),
    }
    if content_hash:
        row["ContentHash"] = content_hash
    replaced = False
    for idx, existing in enumerate(rows):
        if Path(existing["SourceFile"]).stem == image_id:
            if content_hash is None and existing.get("ContentHash"):
                row["ContentHash"] = existing["ContentHash"]
            rows[idx] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    _save_meta_rows(user_id, rows)


def _persist_image(
    upload_path: Path,
    image_id: str,
    date_folder: str,
    user_id: str,
) -> tuple[Path, Path]:
    batch_dir = user_photos_dir(user_id, date_folder)
    jpg_dir = batch_dir / "jpg"
    batch_dir.mkdir(parents=True, exist_ok=True)
    jpg_dir.mkdir(parents=True, exist_ok=True)

    suffix = upload_path.suffix.lower()
    if suffix == ".heic":
        dest = batch_dir / f"{image_id}.HEIC"
        shutil.copy2(upload_path, dest)
        jpg_path = jpg_dir / f"{image_id}.jpg"
        convert_heic_to_jpg(dest, jpg_path)
        return dest, jpg_path

    dest = batch_dir / f"{image_id}{suffix or '.jpg'}"
    shutil.copy2(upload_path, dest)
    jpg_path = jpg_dir / f"{image_id}.jpg"
    if suffix in {".jpg", ".jpeg"}:
        shutil.copy2(upload_path, jpg_path)
    else:
        subprocess.run(
            [tool_path("sips"), "-s", "format", "jpeg", str(dest), "--out", str(jpg_path)],
            check=True,
            capture_output=True,
        )
    return dest, jpg_path


def _save_extraction(
    user_id: str,
    image_id: str,
    result: ExtractionResult,
    *,
    source: str,
) -> Path:
    directory = user_extractions_dir(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{image_id}.json"
    payload = {
        "image_id": image_id,
        "user_id": user_id,
        "source": source,
        "extracted_at": datetime.now(TORONTO).isoformat(timespec="seconds"),
        "extractor": result.extractor,
        "image_path": result.image_path,
        "meta": result.meta.model_dump(mode="json"),
        "products": [p.to_product_dict() for p in result.products],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def _duplicate_response(
    *,
    duplicate_of: str,
    content_hash: str,
    duplicate_action: str | None,
) -> dict | None:
    if duplicate_action == "skip":
        return {
            "duplicate": True,
            "duplicate_of": duplicate_of,
            "content_hash": content_hash,
            "skipped": True,
            "image_id": duplicate_of,
            "products": [],
            "product_count": 0,
            "meta": {},
            "source": "upload",
            "extractor": None,
            "needs_store_label": False,
        }
    if duplicate_action is None:
        return {
            "duplicate": True,
            "duplicate_of": duplicate_of,
            "content_hash": content_hash,
            "action_required": True,
        }
    return None


def ingest_upload(
    upload_path: Path,
    *,
    user_id: str,
    image_id: str | None = None,
    source: str = "upload",
    api_key: str | None = None,
    duplicate_action: str | None = None,
) -> dict:
    """Save an uploaded photo for a user, extract products, rebuild user catalog."""
    user_root(user_id).mkdir(parents=True, exist_ok=True)

    content_hash = file_content_hash(upload_path)
    duplicate_of = find_exact_duplicate(user_id, content_hash)
    if duplicate_of:
        duplicate_result = _duplicate_response(
            duplicate_of=duplicate_of,
            content_hash=content_hash,
            duplicate_action=duplicate_action,
        )
        if duplicate_result is not None:
            return duplicate_result
        if duplicate_action == "replace":
            delete_photo(user_id, duplicate_of)
            image_id = duplicate_of

    image_id = image_id or next_image_id(user_id)

    exif = extract_exif(upload_path) if upload_path.exists() else {}
    raw_dt = exif.get("DateTimeOriginal")
    date_folder = date_folder_from_exif(raw_dt) or _today_folder()

    saved_path, _jpg_path = _persist_image(upload_path, image_id, date_folder, user_id)
    _upsert_meta(user_id, image_id, str(saved_path.relative_to(ROOT)), exif, content_hash=content_hash)
    set_content_hash(user_id, image_id, content_hash)

    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)
    auto_assign_store_from_gps(
        user_id,
        image_id,
        exif.get("GPSLatitude"),
        exif.get("GPSLongitude"),
        user_stores,
    )

    existing_products = build_product_lines(user_id=user_id)

    result = extract_from_upload(
        saved_path,
        image_id=image_id,
        api_key=api_key,
        prompt_variant="receipt" if source == "receipt" else "shelf",
    )
    extraction_path = _save_extraction(user_id, image_id, result, source=source)
    product_count = write_user_products_jsonl(user_id)

    from grocery_extract.photo_stores import image_needs_store_label

    needs_store_label = image_needs_store_label(
        user_id,
        image_id,
        exif.get("GPSLatitude"),
        exif.get("GPSLongitude"),
        user_stores,
    )

    all_products = build_product_lines(user_id=user_id)
    new_rows = [row for row in all_products if row["image_id"] == image_id]
    overlaps = overlapping_product_keys(new_rows, existing_products)

    return {
        "image_id": image_id,
        "date_folder": date_folder,
        "image_path": f"api/media/{image_id}",
        "source": source,
        "extraction_path": str(extraction_path.relative_to(ROOT)),
        "products": [p.model_dump(mode="json") for p in result.products],
        "meta": {
            **result.meta.model_dump(mode="json"),
            "captured_at": captured_at_from_exif(raw_dt),
        },
        "product_count": product_count,
        "extractor": result.extractor,
        "needs_store_label": needs_store_label,
        "content_hash": content_hash,
        "extraction_empty": len(result.products) == 0,
        "overlapping_products": overlaps,
        "duplicate": False,
    }


def ingest_upload_batch(
    upload_paths: list[Path],
    *,
    user_id: str,
    source: str = "receipt",
    api_key: str | None = None,
    duplicate_action: str | None = None,
    max_workers: int | None = None,
) -> list[dict]:
    image_ids = allocate_image_ids(user_id, len(upload_paths))
    workers = max(1, min(max_workers or DEFAULT_UPLOAD_WORKERS, len(upload_paths)))
    if workers == 1:
        results = [
            ingest_upload(
                upload_path,
                user_id=user_id,
                image_id=image_id,
                source=source,
                api_key=api_key,
                duplicate_action=duplicate_action,
            )
            for upload_path, image_id in zip(upload_paths, image_ids, strict=True)
        ]
    else:
        results: list[dict | None] = [None] * len(upload_paths)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(
                    ingest_upload,
                    upload_path,
                    user_id=user_id,
                    image_id=image_id,
                    source=source,
                    api_key=api_key,
                    duplicate_action=duplicate_action,
                ): index
                for index, (upload_path, image_id) in enumerate(
                    zip(upload_paths, image_ids, strict=True)
                )
            }
            for future in as_completed(future_map):
                index = future_map[future]
                results[index] = future.result()
        results = [result for result in results if result is not None]

    write_user_products_jsonl(user_id)
    return results
