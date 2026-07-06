from __future__ import annotations

import atexit
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

DEFAULT_EXTRACT_CONCURRENCY = 4
DEFAULT_UPLOAD_WORKERS = 4

EXTRACT_CONCURRENCY = int(os.environ.get("GROCERY_EXTRACT_CONCURRENCY", str(DEFAULT_EXTRACT_CONCURRENCY)))
UPLOAD_WORKERS = int(os.environ.get("GROCERY_UPLOAD_WORKERS", str(DEFAULT_UPLOAD_WORKERS)))

logger = logging.getLogger(__name__)

_llm_semaphore = threading.Semaphore(EXTRACT_CONCURRENCY)
_executor = ThreadPoolExecutor(max_workers=UPLOAD_WORKERS, thread_name_prefix="grocery-extract")
_on_complete_callbacks: list[Callable[[str, dict[str, Any]], None]] = []
_stats_lock = threading.Lock()
_pending_jobs = 0
_last_failure_at: float | None = None
_last_failure_error_type: str | None = None


@dataclass(frozen=True)
class ExtractionJob:
    user_id: str
    image_id: str
    source: str
    api_key: str | None
    existing_products: list[dict[str, Any]]
    user_stores: list[dict[str, Any]]
    exif: dict[str, Any]
    date_folder: str
    captured_at: str | None
    store_location_id: str | None
    content_hash: str
    request_id: str | None = None
    extract_backend: str | None = None


def register_extraction_complete(callback: Callable[[str, dict[str, Any]], None]) -> None:
    _on_complete_callbacks.append(callback)


def record_extraction_failure(error_type: str) -> None:
    global _last_failure_at, _last_failure_error_type
    with _stats_lock:
        _last_failure_at = time.time()
        _last_failure_error_type = error_type


def worker_stats() -> dict[str, Any]:
    with _stats_lock:
        stats: dict[str, Any] = {
            "extract_concurrency": EXTRACT_CONCURRENCY,
            "upload_workers": UPLOAD_WORKERS,
            "pending_jobs": _pending_jobs,
        }
        if _last_failure_at is not None:
            stats["last_extraction_failure_at"] = datetime.fromtimestamp(
                _last_failure_at,
                tz=timezone.utc,
            ).isoformat()
            stats["last_extraction_failure_type"] = _last_failure_error_type
    return stats


def enqueue_extraction(job: ExtractionJob, runner: Callable[[ExtractionJob], dict[str, Any]]) -> None:
    _executor.submit(_run_job, job, runner)


def _run_job(job: ExtractionJob, runner: Callable[[ExtractionJob], dict[str, Any]]) -> None:
    global _pending_jobs
    with _stats_lock:
        _pending_jobs += 1
    try:
        with _llm_semaphore:
            try:
                result = runner(job)
            except Exception as err:
                record_extraction_failure(type(err).__name__)
                logger.exception(
                    "extraction_worker_failed photo_id=%s user_id=%s request_id=%s",
                    job.image_id,
                    job.user_id,
                    job.request_id or "-",
                )
                result = {
                    "image_id": job.image_id,
                    "extraction_status": "failed",
                    "extraction_error": str(err),
                }
        for callback in _on_complete_callbacks:
            try:
                callback(job.user_id, result)
            except Exception:
                logger.exception(
                    "extraction_callback_failed photo_id=%s user_id=%s request_id=%s",
                    job.image_id,
                    job.user_id,
                    job.request_id or "-",
                )
    finally:
        with _stats_lock:
            _pending_jobs -= 1


def shutdown_worker() -> None:
    _executor.shutdown(wait=False)


atexit.register(shutdown_worker)
