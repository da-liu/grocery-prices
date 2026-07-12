from __future__ import annotations

import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from extract_server.db import (
    blob_key,
    find_photo_by_content_hash,
    get_conn,
    get_photo_blob_path,
    get_photos_extraction_status,
    list_user_stores_as_dicts,
    new_photo_ids,
    record_photo_extraction_failure,
    save_photo,
    save_photo_extraction,
    set_extraction_pipeline_status,
)
from extract_server.db._ids import normalize_photo_suffix
from extract_server.extraction.delete import delete_photo
from extract_server.extraction.duplicate import file_content_hash
from extract_server.extraction.worker import ExtractionJob, enqueue_extraction, record_extraction_failure
from extract_server.core.request import get_request_id
from extract_server.extraction.pipeline import extract_from_upload
from extract_server.extraction.photo_stores import image_needs_store_label
from extract_server.extraction.stores import store_from_gps
from extract_server.extraction.paths import user_photos_dir, user_root

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

    stored_suffix = normalize_photo_suffix(suffix)
    dest = batch_dir / f"{image_id}{stored_suffix}"
    shutil.copy2(upload_path, dest)
    return blob_key(user_id, date_folder, image_id, stored_suffix)


def _result(
    *,
    image_id: str,
    extraction_status: str,
    product_count: int = 0,
    needs_store_label: bool = False,
    extraction_empty: bool = False,
    duplicate_of: str | None = None,
    skipped: bool = False,
    status: str | None = None,
    extraction_error: str | None = None,
) -> dict:
    payload: dict[str, Any] = {
        "image_id": image_id,
        "product_count": product_count,
        "needs_store_label": needs_store_label,
        "extraction_empty": extraction_empty,
        "extraction_status": extraction_status,
    }
    if duplicate_of is not None:
        payload["duplicate_of"] = duplicate_of
    if skipped:
        payload["skipped"] = True
    if status is not None:
        payload["status"] = status
    if extraction_error is not None:
        payload["extraction_error"] = extraction_error
    return payload


def _duplicate_response(
    *,
    duplicate_of: str,
    duplicate_action: str | None,
) -> dict | None:
    if duplicate_action == "skip":
        return _result(
            image_id=duplicate_of,
            extraction_status="done",
            duplicate_of=duplicate_of,
            skipped=True,
        )
    if duplicate_action is None:
        return {
            "duplicate_of": duplicate_of,
            "action_required": True,
        }
    return None


@dataclass
class ExtractedPhoto:
    products: list[dict]
    product_count: int
    extractor: str
    photo_type: str | None
    llm_ms: int | None
    other_ms: int | None
    model: str | None


def persist_upload(
    upload_path: Path,
    *,
    user_id: str,
    image_id: str,
    duplicate_action: str | None,
    user_stores: list[dict[str, Any]],
    client_exif: dict | None,
    api_key: str | None,
) -> tuple[dict, ExtractionJob | None]:
    """Stage 1: save blob + photo row. Returns API payload and optional extract job."""
    user_root(user_id).mkdir(parents=True, exist_ok=True)

    content_hash = file_content_hash(upload_path)
    duplicate_of = find_photo_by_content_hash(user_id, content_hash)
    if duplicate_of:
        duplicate_result = _duplicate_response(
            duplicate_of=duplicate_of,
            duplicate_action=duplicate_action,
        )
        if duplicate_result is not None:
            return duplicate_result, None
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

    result = _result(
        image_id=image_id,
        extraction_status="pending",
        needs_store_label=needs_store_label,
    )
    job = ExtractionJob(
        user_id=user_id,
        image_id=image_id,
        api_key=api_key,
        user_stores=user_stores,
        exif=exif,
        date_folder=date_folder,
        content_hash=content_hash,
    )
    return result, job


def extract_and_save(job: ExtractionJob) -> ExtractedPhoto:
    """Stage 2: call LLM and write extraction/products to DB."""
    image_path = get_photo_blob_path(job.user_id, job.image_id)
    if image_path is None:
        raise FileNotFoundError(f"Stored image not found for {job.image_id}")

    extraction_start = time.perf_counter()
    result = extract_from_upload(
        image_path,
        api_key=job.api_key,
    )
    products = [product.to_product_dict() for product in result.products]
    photo_type = result.photo_type
    timing = result.timing
    if timing is not None:
        llm_ms, other_ms, model = timing.llm_ms, timing.other_ms, timing.model
    else:
        llm_ms, model = None, None
        other_ms = int((time.perf_counter() - extraction_start) * 1000)
    product_count = save_photo_extraction(
        job.user_id,
        job.image_id,
        extractor=result.extractor,
        raw_response=result.raw_response,
        products=products,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        photo_type=photo_type,
    )
    return ExtractedPhoto(
        products=products,
        product_count=product_count,
        extractor=result.extractor,
        photo_type=photo_type,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
    )


def match_extracted_products(job: ExtractionJob, *, product_count: int) -> str:
    """Stage 3: match extracted products to catalog. Returns pipeline_status."""
    if product_count == 0:
        return "matched"
    try:
        from extract_server.extraction.match_catalog import match_photo

        match_photo(job.user_id, job.image_id, api_key=job.api_key)
        set_extraction_pipeline_status(job.user_id, job.image_id, "matched")
        return "matched"
    except Exception:
        logger.exception(
            "matching_failed photo_id=%s user_id=%s request_id=%s",
            job.image_id,
            job.user_id,
            job.request_id or "-",
        )
        set_extraction_pipeline_status(job.user_id, job.image_id, "match_failed")
        return "match_failed"


def run_extraction_pipeline(job: ExtractionJob) -> dict:
    """Background worker entry: extract → save → match."""
    request_id = job.request_id or "-"
    logger.info(
        "extraction_started photo_id=%s user_id=%s request_id=%s",
        job.image_id,
        job.user_id,
        request_id,
    )
    try:
        extracted = extract_and_save(job)
        pipeline_status = match_extracted_products(
            job,
            product_count=extracted.product_count,
        )
        logger.info(
            "extraction_complete photo_id=%s user_id=%s request_id=%s llm_ms=%s other_ms=%s "
            "photo_type=%s model=%s products=%s pipeline_status=%s",
            job.image_id,
            job.user_id,
            request_id,
            extracted.llm_ms,
            extracted.other_ms,
            extracted.photo_type,
            extracted.model,
            extracted.product_count,
            pipeline_status,
        )

        needs_store_label = image_needs_store_label(
            job.user_id,
            job.image_id,
            job.exif.get("GPSLatitude"),
            job.exif.get("GPSLongitude"),
            job.user_stores,
        )

        return _result(
            image_id=job.image_id,
            extraction_status="done",
            product_count=extracted.product_count,
            needs_store_label=needs_store_label,
            extraction_empty=extracted.product_count == 0,
            status=pipeline_status,
        )
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
        return _result(
            image_id=job.image_id,
            extraction_status="failed",
            status="failed",
            extraction_error=str(err),
            extraction_empty=True,
        )


def _persist_uploads_parallel(
    items: list[tuple[Path, str, dict | None]],
    *,
    persist: Callable[..., tuple[dict, ExtractionJob | None]],
    workers: int,
) -> list[tuple[dict, ExtractionJob | None]]:
    if workers == 1:
        return [
            persist(path, image_id=image_id, client_exif=exif)
            for path, image_id, exif in items
        ]

    slotted: list[tuple[dict, ExtractionJob | None] | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(persist, path, image_id=image_id, client_exif=exif): index
            for index, (path, image_id, exif) in enumerate(items)
        }
        for future in as_completed(future_map):
            slotted[future_map[future]] = future.result()
    return [item for item in slotted if item is not None]


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
) -> list[dict]:
    """Persist uploads, then enqueue extract→match for each new photo."""
    image_ids = new_photo_ids(len(upload_paths))
    workers = max(1, min(max_workers or DEFAULT_UPLOAD_WORKERS, len(upload_paths)))
    user_stores = list_user_stores_as_dicts(user_id)
    exifs = client_exifs if client_exifs is not None else [None] * len(upload_paths)
    if len(exifs) != len(upload_paths):
        raise ValueError("client_exifs length must match upload_paths")

    items = list(zip(upload_paths, image_ids, exifs, strict=True))
    persist = partial(
        persist_upload,
        user_id=user_id,
        duplicate_action=duplicate_action,
        user_stores=user_stores,
        api_key=api_key,
    )
    accepted = _persist_uploads_parallel(items, persist=persist, workers=workers)

    resolved_request_id = request_id or get_request_id()
    results: list[dict] = []
    for result, job in accepted:
        results.append(result)
        if enqueue and job is not None:
            enqueue_extraction(
                replace(job, request_id=resolved_request_id),
                run_extraction_pipeline,
            )
    return results


def build_status_response(user_id: str, image_ids: list[str]) -> list[dict]:
    conn = get_conn()
    user_stores = list_user_stores_as_dicts(user_id, conn=conn)
    return get_photos_extraction_status(
        user_id,
        image_ids,
        conn=conn,
        user_stores=user_stores,
    )
