from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from grocery_extract.exif import (
    captured_at_from_exif,
    convert_heic_to_jpg,
    date_folder_from_exif,
    extract_exif,
    tool_path,
)
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.photo_stores import auto_assign_store_from_gps
from grocery_extract.products_builder import write_user_products_jsonl
from grocery_extract.schema import ExtractionResult
from grocery_extract.user_paths import (
    user_extractions_dir,
    user_meta_path,
    user_photos_dir,
    user_root,
)

ROOT = Path(__file__).resolve().parents[1]
TORONTO = ZoneInfo("America/Toronto")


def _today_folder() -> str:
    return datetime.now(TORONTO).strftime("%Y_%m_%d")


def next_image_id(user_id: str) -> str:
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
    return f"IMG_{max_num + 1:04d}"


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


def _upsert_meta(user_id: str, image_id: str, source_file: str, exif: dict) -> None:
    rows = _load_meta_rows(user_id)
    row = {
        "SourceFile": source_file,
        "GPSLatitude": exif.get("GPSLatitude"),
        "GPSLongitude": exif.get("GPSLongitude"),
        "DateTimeOriginal": exif.get("DateTimeOriginal"),
    }
    replaced = False
    for idx, existing in enumerate(rows):
        if Path(existing["SourceFile"]).stem == image_id:
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


def ingest_upload(
    upload_path: Path,
    *,
    user_id: str,
    image_id: str | None = None,
    source: str = "upload",
    api_key: str | None = None,
) -> dict:
    """Save an uploaded photo for a user, extract products, rebuild user catalog."""
    user_root(user_id).mkdir(parents=True, exist_ok=True)
    image_id = image_id or next_image_id(user_id)

    exif = extract_exif(upload_path) if upload_path.exists() else {}
    raw_dt = exif.get("DateTimeOriginal")
    date_folder = date_folder_from_exif(raw_dt) or _today_folder()

    saved_path, _jpg_path = _persist_image(upload_path, image_id, date_folder, user_id)
    _upsert_meta(user_id, image_id, str(saved_path.relative_to(ROOT)), exif)

    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)
    auto_assign_store_from_gps(
        user_id,
        image_id,
        exif.get("GPSLatitude"),
        exif.get("GPSLongitude"),
        user_stores,
    )

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
    }


def ingest_upload_batch(
    upload_paths: list[Path],
    *,
    user_id: str,
    source: str = "receipt",
    api_key: str | None = None,
) -> list[dict]:
    results = [
        ingest_upload(upload_path, user_id=user_id, source=source, api_key=api_key)
        for upload_path in upload_paths
    ]
    write_user_products_jsonl(user_id)
    return results
