from __future__ import annotations

import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from extract_server.db import (
    blob_key,
    find_photo_by_content_hash,
    get_photos_extraction_status,
    new_photo_ids,
    record_photo_extraction_failure,
    save_photo,
    save_photo_extraction,
)
from extract_server.grocery_extract.delete import delete_photo
from extract_server.grocery_extract.duplicate import file_content_hash
from extract_server.grocery_extract.extract_worker import ExtractionJob, enqueue_extraction, record_extraction_failure
from extract_server.grocery_extract.request_context import get_request_id
from extract_server.grocery_extract.pipeline import extract_from_upload
from extract_server.grocery_extract.photo_stores import image_needs_store_label
from extract_server.grocery_extract.stores import store_from_gps
from extract_server.grocery_extract.user_paths import user_photos_dir, user_root

TORONTO = ZoneInfo("America/Toronto")
DEFAULT_UPLOAD_WORKERS = int(os.environ.get("GROCERY_UPLOAD_WORKERS", "4"))
logger = logging.getLogger(__name__)


def _today_folder() -> str:
    return datetime.now(TORONTO).strftime("%Y_%m_%d")


def _persist_image(
    upload_path: Path,
    image_id: str,
    date_folder: str,
    user_id: str,
) -> str:
    batch_dir = user_photos_dir(user_id, date_folder)
    batch_dir.mkdir(parents=True, exist_ok=True)

    suffix = upload_path.suffix.lower()
    if suffix in {".heic", ".heif"}:
        raise ValueError(f"Unsupported image type: {suffix}")
    if suffix != ".webp":
        raise ValueError(f"Only WebP uploads are supported, got: {suffix or '(none)'}")

    dest = batch_dir / f"{image_id}.webp"
    shutil.copy2(upload_path, dest)
    return blob_key(user_id, date_folder, image_id)


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


def _persist_one_upload(
    upload_path: Path,
    *,
    user_id: str,
    image_id: str,
    duplicate_action: str | None,
    user_stores: list[dict[str, Any]],
    client_exif: dict | None,
    extract_backend: str | None,
) -> dict:
    """Persist one uploaded photo and return quickly with extraction_status=pending."""
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

    exif = client_exif if isinstance(client_exif, dict) else {}
    captured_at = exif.get("captured_at")
    date_folder = exif.get("date_folder") or _today_folder()

    key = _persist_image(upload_path, image_id, date_folder, user_id)

    store_location_id = None
    lat = exif.get("GPSLatitude")
    lon = exif.get("GPSLongitude")
    if lat is not None and lon is not None:
        matched = store_from_gps(lat, lon, user_stores)
        if matched:
            store_location_id = matched["id"]

    save_photo(
        user_id,
        photo_id=image_id,
        blob_key=key,
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
        "duplicate": False,
        "extraction_status": "pending",
        "_job": {
            "exif": exif,
            "date_folder": date_folder,
            "captured_at": captured_at,
            "store_location_id": store_location_id,
            "user_stores": user_stores,
            "extract_backend": extract_backend,
        },
    }


def run_extraction(job: ExtractionJob) -> dict:
    """Background worker: LLM extraction and catalog finalize."""
    request_id = job.request_id or "-"
    logger.info(
        "extraction_started photo_id=%s user_id=%s request_id=%s",
        job.image_id,
        job.user_id,
        request_id,
    )
    from extract_server.db import get_photo_blob_path

    image_path = get_photo_blob_path(job.user_id, job.image_id)
    if image_path is None:
        raise FileNotFoundError(f"Stored image not found for {job.image_id}")
    try:
        extraction_start = time.perf_counter()
        result = extract_from_upload(
            image_path,
            image_id=job.image_id,
            api_key=job.api_key,
            backend=job.extract_backend,
            exif=job.exif,
        )
        products = [product.to_product_dict() for product in result.products]
        photo_type = result.photo_type
        timing = result.timing
        if timing is not None:
            llm_ms = timing.llm_ms
            other_ms = timing.other_ms
        else:
            elapsed_ms = int((time.perf_counter() - extraction_start) * 1000)
            llm_ms = None
            other_ms = elapsed_ms
        product_count = save_photo_extraction(
            job.user_id,
            job.image_id,
            extractor=result.extractor,
            raw_response=result.raw_response,
            products=products,
            llm_ms=llm_ms,
            other_ms=other_ms,
            model=timing.model if timing else None,
            photo_type=photo_type,
        )
        logger.info(
            "extraction_complete photo_id=%s user_id=%s request_id=%s llm_ms=%s other_ms=%s "
            "photo_type=%s model=%s products=%s",
            job.image_id,
            job.user_id,
            request_id,
            llm_ms,
            other_ms,
            photo_type,
            timing.model if timing else None,
            product_count,
        )

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
            "duplicate": False,
            "extraction_status": "done",
            "detected_receipt": photo_type == "receipt",
        }
    except Exception as err:
        record_extraction_failure(type(err).__name__)
        logger.exception(
            "extraction_failed photo_id=%s user_id=%s request_id=%s error_type=%s",
            job.image_id,
            job.user_id,
            request_id,
            type(err).__name__,
        )
        record_photo_extraction_failure(job.user_id, job.image_id, str(err))
        return {
            "image_id": job.image_id,
            "extraction_status": "failed",
            "extraction_error": str(err),
            "product_count": 0,
            "products": [],
            "extraction_empty": True,
            "needs_store_label": False,
            "meta": {},
            "duplicate": False,
        }


def _job_from_accept_result(result: dict, *, user_id: str, api_key: str | None) -> ExtractionJob | None:
    if result.get("skipped") or result.get("duplicate"):
        return None
    job_data = result.get("_job")
    if job_data is None:
        return None
    return ExtractionJob(
        user_id=user_id,
        image_id=result["image_id"],
        api_key=api_key,
        user_stores=job_data["user_stores"],
        exif=job_data["exif"],
        date_folder=job_data["date_folder"],
        captured_at=job_data["captured_at"],
        store_location_id=job_data["store_location_id"],
        content_hash=result["content_hash"],
        request_id=result.get("request_id"),
        extract_backend=job_data.get("extract_backend"),
    )


def accept_upload_batch(
    upload_paths: list[Path],
    *,
    user_id: str,
    duplicate_action: str | None = None,
    max_workers: int | None = None,
    api_key: str | None = None,
    enqueue: bool = True,
    client_exifs: list[dict | None] | None = None,
    request_id: str | None = None,
    extract_backend: str | None = None,
) -> list[dict]:
    image_ids = new_photo_ids(len(upload_paths))
    workers = max(1, min(max_workers or DEFAULT_UPLOAD_WORKERS, len(upload_paths)))

    from extract_server.db import list_user_stores_as_dicts

    user_stores = list_user_stores_as_dicts(user_id)

    exifs = client_exifs if client_exifs is not None else [None] * len(upload_paths)
    if len(exifs) != len(upload_paths):
        raise ValueError("client_exifs length must match upload_paths")

    def accept_one(
        upload_path: Path,
        image_id: str,
        exif_payload: dict | None = None,
    ) -> dict:
        return _persist_one_upload(
            upload_path,
            user_id=user_id,
            image_id=image_id,
            duplicate_action=duplicate_action,
            user_stores=user_stores,
            client_exif=exif_payload,
            extract_backend=extract_backend,
        )

    if workers == 1:
        results = [
            accept_one(upload_path, image_id, exif_payload)
            for upload_path, image_id, exif_payload in zip(
                upload_paths,
                image_ids,
                exifs,
                strict=True,
            )
        ]
    else:
        results = [None] * len(upload_paths)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(accept_one, upload_path, image_id, exif_payload): index
                for index, (upload_path, image_id, exif_payload) in enumerate(
                    zip(upload_paths, image_ids, exifs, strict=True)
                )
            }
            for future in as_completed(future_map):
                index = future_map[future]
                results[index] = future.result()
        results = [result for result in results if result is not None]

    resolved_request_id = request_id or get_request_id()

    if enqueue:
        for result in results:
            if resolved_request_id:
                result["request_id"] = resolved_request_id
            job = _job_from_accept_result(result, user_id=user_id, api_key=api_key)
            if job is not None:
                enqueue_extraction(job, run_extraction)

    for result in results:
        result.pop("_job", None)
        result.pop("request_id", None)

    return results


def build_status_response(user_id: str, image_ids: list[str]) -> list[dict]:
    from extract_server.users_db import get_conn
    from extract_server.db import list_user_stores_as_dicts

    conn = get_conn()
    user_stores = list_user_stores_as_dicts(user_id, conn=conn)
    statuses = get_photos_extraction_status(user_id, image_ids, conn=conn)

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
                store_location_id=row.get("store_location_id") or meta.get("store_location_id"),
            )
        else:
            row.setdefault("needs_store_label", False)
        enriched.append(row)
    return enriched
