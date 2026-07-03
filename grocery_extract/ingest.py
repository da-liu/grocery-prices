from __future__ import annotations

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from grocery_extract.catalog_db import (
    allocate_image_ids,
    blob_keys,
    finalize_photo_extraction,
    find_photo_by_content_hash,
    get_photos_extraction_status,
    list_products_for_matching,
    next_image_id,
    photo_type_from_ingest_source,
    save_photo_pending,
    set_extraction_status,
)
from grocery_extract.delete import delete_photo
from grocery_extract.duplicate import file_content_hash
from grocery_extract.exif import (
    captured_at_from_exif,
    convert_heic_to_jpg,
    date_folder_from_exif,
    extract_exif,
    tool_path,
)
from grocery_extract.extract_worker import ExtractionJob, enqueue_extraction
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.photo_stores import image_needs_store_label
from grocery_extract.product_matching import overlapping_product_keys, products_to_match_rows
from grocery_extract.stores import store_from_gps
from grocery_extract.user_paths import user_photos_dir, user_root

TORONTO = ZoneInfo("America/Toronto")
DEFAULT_UPLOAD_WORKERS = int(os.environ.get("GROCERY_UPLOAD_WORKERS", "4"))


def _today_folder() -> str:
    return datetime.now(TORONTO).strftime("%Y_%m_%d")


def _persist_image(
    upload_path: Path,
    image_id: str,
    date_folder: str,
    user_id: str,
) -> tuple[str | None, str, str]:
    batch_dir = user_photos_dir(user_id, date_folder)
    jpg_dir = batch_dir / "jpg"
    batch_dir.mkdir(parents=True, exist_ok=True)
    jpg_dir.mkdir(parents=True, exist_ok=True)

    suffix = upload_path.suffix.lower()
    jpg_path = jpg_dir / f"{image_id}.jpg"

    if suffix == ".heic":
        dest = batch_dir / f"{image_id}.HEIC"
        shutil.copy2(upload_path, dest)
        convert_heic_to_jpg(dest, jpg_path)
        original_key, jpeg_key = blob_keys(user_id, date_folder, image_id, original_suffix=".HEIC")
        return original_key, jpeg_key, suffix

    if suffix in {".jpg", ".jpeg"}:
        shutil.copy2(upload_path, jpg_path)
        original_key, jpeg_key = blob_keys(user_id, date_folder, image_id, original_suffix=suffix)
        return jpeg_key, jpeg_key, suffix

    dest = batch_dir / f"{image_id}{suffix or '.jpg'}"
    shutil.copy2(upload_path, dest)
    subprocess.run(
        [tool_path("sips"), "-s", "format", "jpeg", str(dest), "--out", str(jpg_path)],
        check=True,
        capture_output=True,
    )
    original_key, jpeg_key = blob_keys(user_id, date_folder, image_id, original_suffix=suffix or ".jpg")
    return original_key, jpeg_key, suffix


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
            "extraction_status": "done",
        }
    if duplicate_action is None:
        return {
            "duplicate": True,
            "duplicate_of": duplicate_of,
            "content_hash": content_hash,
            "action_required": True,
        }
    return None


def _location_for_accept(
    *,
    photo_type: str,
    exif: dict[str, Any],
    user_stores: list[dict[str, Any]],
    store_location_id: str | None,
) -> dict[str, Any]:
    from grocery_extract.catalog_db import _location_for_photo

    return _location_for_photo(
        {
            "gps_latitude": exif.get("GPSLatitude"),
            "gps_longitude": exif.get("GPSLongitude"),
            "store_location_id": store_location_id,
            "type": photo_type,
        },
        user_stores=user_stores,
        user_store_by_id={store["id"]: store for store in user_stores},
    )


def accept_upload(
    upload_path: Path,
    *,
    user_id: str,
    image_id: str | None = None,
    source: str = "upload",
    duplicate_action: str | None = None,
    existing_products: list[dict[str, Any]] | None = None,
    user_stores: list[dict[str, Any]] | None = None,
) -> dict:
    """Persist an uploaded photo and return quickly with extraction_status=pending."""
    user_root(user_id).mkdir(parents=True, exist_ok=True)

    content_hash = file_content_hash(upload_path)
    duplicate_of = find_photo_by_content_hash(user_id, content_hash)
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
    photo_type = photo_type_from_ingest_source(source)

    exif = extract_exif(upload_path) if upload_path.exists() else {}
    raw_dt = exif.get("DateTimeOriginal")
    date_folder = date_folder_from_exif(raw_dt) or _today_folder()
    captured_at = captured_at_from_exif(raw_dt)

    original_key, jpeg_key, _suffix = _persist_image(upload_path, image_id, date_folder, user_id)

    if user_stores is None:
        from grocery_extract.user_stores_db import list_user_stores_as_dicts

        user_stores = list_user_stores_as_dicts(user_id)

    store_location_id = None
    lat = exif.get("GPSLatitude")
    lon = exif.get("GPSLongitude")
    if photo_type == "shelf" and lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            store_location_id = matched["id"]

    save_photo_pending(
        user_id,
        photo_id=image_id,
        photo_type=photo_type,
        original_blob_key=original_key,
        jpeg_blob_key=jpeg_key,
        content_hash=content_hash,
        gps_latitude=lat,
        gps_longitude=lon,
        captured_at=captured_at,
        store_location_id=store_location_id,
    )

    needs_store_label = image_needs_store_label(
        user_id,
        image_id,
        lat,
        lon,
        user_stores,
    )

    return {
        "image_id": image_id,
        "date_folder": date_folder,
        "image_path": f"api/media/{image_id}",
        "source": source,
        "products": [],
        "product_count": 0,
        "meta": {
            "gps_latitude": lat,
            "gps_longitude": lon,
            "captured_at": captured_at,
        },
        "extractor": None,
        "needs_store_label": needs_store_label,
        "content_hash": content_hash,
        "extraction_empty": False,
        "overlapping_products": [],
        "duplicate": False,
        "extraction_status": "pending",
        "_job": {
            "exif": exif,
            "photo_type": photo_type,
            "date_folder": date_folder,
            "captured_at": captured_at,
            "store_location_id": store_location_id,
            "existing_products": existing_products or [],
            "user_stores": user_stores,
        },
    }


def run_extraction(job: ExtractionJob) -> dict:
    """Background worker: LLM extraction and catalog finalize."""
    set_extraction_status(job.user_id, job.image_id, "processing")

    jpg_path = user_photos_dir(job.user_id, job.date_folder) / "jpg" / f"{job.image_id}.jpg"
    try:
        result = extract_from_upload(
            jpg_path,
            image_id=job.image_id,
            api_key=job.api_key,
            prompt_variant="receipt" if job.photo_type == "receipt" else "shelf",
            exif=job.exif,
            skip_normalize=True,
        )
        products = [product.to_product_dict() for product in result.products]
        product_count = finalize_photo_extraction(
            job.user_id,
            job.image_id,
            extractor=result.extractor,
            raw_response=result.raw_response,
            products=products,
        )

        location = _location_for_accept(
            photo_type=job.photo_type,
            exif=job.exif,
            user_stores=job.user_stores,
            store_location_id=job.store_location_id,
        )
        new_rows = products_to_match_rows(
            products,
            image_id=job.image_id,
            location=location,
            captured_at=job.captured_at,
        )
        overlaps = overlapping_product_keys(new_rows, job.existing_products)

        needs_store_label = image_needs_store_label(
            job.user_id,
            job.image_id,
            job.exif.get("GPSLatitude"),
            job.exif.get("GPSLongitude"),
            job.user_stores,
        )

        return {
            "image_id": job.image_id,
            "date_folder": job.date_folder,
            "image_path": f"api/media/{job.image_id}",
            "source": job.source,
            "products": products,
            "meta": {
                **result.meta.model_dump(mode="json"),
                "captured_at": job.captured_at,
            },
            "product_count": product_count,
            "extractor": result.extractor,
            "needs_store_label": needs_store_label,
            "content_hash": job.content_hash,
            "extraction_empty": len(products) == 0,
            "overlapping_products": overlaps,
            "duplicate": False,
            "extraction_status": "done",
        }
    except Exception as err:
        set_extraction_status(job.user_id, job.image_id, "failed", error=str(err))
        return {
            "image_id": job.image_id,
            "extraction_status": "failed",
            "extraction_error": str(err),
            "product_count": 0,
            "products": [],
            "extraction_empty": True,
            "overlapping_products": [],
            "needs_store_label": False,
            "meta": {},
            "duplicate": False,
        }


def _job_from_accept_result(result: dict, *, user_id: str, source: str, api_key: str | None) -> ExtractionJob | None:
    if result.get("extraction_status") != "pending":
        return None
    job_data = result.get("_job")
    if job_data is None:
        return None
    return ExtractionJob(
        user_id=user_id,
        image_id=result["image_id"],
        source=source,
        api_key=api_key,
        existing_products=job_data["existing_products"],
        user_stores=job_data["user_stores"],
        exif=job_data["exif"],
        photo_type=job_data["photo_type"],
        date_folder=job_data["date_folder"],
        captured_at=job_data["captured_at"],
        store_location_id=job_data["store_location_id"],
        content_hash=result["content_hash"],
    )


def accept_upload_batch(
    upload_paths: list[Path],
    *,
    user_id: str,
    source: str = "receipt",
    duplicate_action: str | None = None,
    max_workers: int | None = None,
    api_key: str | None = None,
    enqueue: bool = True,
) -> list[dict]:
    image_ids = allocate_image_ids(user_id, len(upload_paths))
    workers = max(1, min(max_workers or DEFAULT_UPLOAD_WORKERS, len(upload_paths)))

    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)
    existing_products = list_products_for_matching(user_id)

    def accept_one(upload_path: Path, image_id: str) -> dict:
        return accept_upload(
            upload_path,
            user_id=user_id,
            image_id=image_id,
            source=source,
            duplicate_action=duplicate_action,
            existing_products=existing_products,
            user_stores=user_stores,
        )

    if workers == 1:
        results = [
            accept_one(upload_path, image_id)
            for upload_path, image_id in zip(upload_paths, image_ids, strict=True)
        ]
    else:
        results = [None] * len(upload_paths)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(accept_one, upload_path, image_id): index
                for index, (upload_path, image_id) in enumerate(
                    zip(upload_paths, image_ids, strict=True)
                )
            }
            for future in as_completed(future_map):
                index = future_map[future]
                results[index] = future.result()
        results = [result for result in results if result is not None]

    if enqueue:
        for result in results:
            job = _job_from_accept_result(result, user_id=user_id, source=source, api_key=api_key)
            if job is not None:
                enqueue_extraction(job, run_extraction)

    for result in results:
        result.pop("_job", None)

    return results


def build_status_response(user_id: str, image_ids: list[str]) -> list[dict]:
    from grocery_extract.user_stores_db import list_user_stores_as_dicts

    statuses = get_photos_extraction_status(user_id, image_ids)
    existing_products = list_products_for_matching(user_id)
    user_stores = list_user_stores_as_dicts(user_id)

    enriched: list[dict] = []
    for status in statuses:
        row = dict(status)
        meta = row.get("meta") or {}
        if row.get("extraction_status") == "done":
            row["needs_store_label"] = image_needs_store_label(
                user_id,
                row["image_id"],
                meta.get("gps_latitude"),
                meta.get("gps_longitude"),
                user_stores,
            )
            if row.get("products"):
                location = {
                    "store": "Unknown store",
                    "latitude": meta.get("gps_latitude"),
                    "longitude": meta.get("gps_longitude"),
                }
                new_rows = products_to_match_rows(
                    row["products"],
                    image_id=row["image_id"],
                    location=location,
                    captured_at=meta.get("captured_at"),
                )
                row["overlapping_products"] = overlapping_product_keys(new_rows, existing_products)
            else:
                row["overlapping_products"] = []
        else:
            row.setdefault("overlapping_products", [])
            row.setdefault("needs_store_label", False)
        enriched.append(row)
    return enriched


# Backward-compatible alias used in older imports/tests.
ingest_upload_batch = accept_upload_batch
