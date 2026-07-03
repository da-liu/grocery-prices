from __future__ import annotations

import atexit
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_EXTRACT_CONCURRENCY = 4
DEFAULT_UPLOAD_WORKERS = 4

EXTRACT_CONCURRENCY = int(os.environ.get("GROCERY_EXTRACT_CONCURRENCY", str(DEFAULT_EXTRACT_CONCURRENCY)))
UPLOAD_WORKERS = int(os.environ.get("GROCERY_UPLOAD_WORKERS", str(DEFAULT_UPLOAD_WORKERS)))

_llm_semaphore = threading.Semaphore(EXTRACT_CONCURRENCY)
_executor = ThreadPoolExecutor(max_workers=UPLOAD_WORKERS, thread_name_prefix="grocery-extract")
_on_complete_callbacks: list[Callable[[str, dict[str, Any]], None]] = []


@dataclass(frozen=True)
class ExtractionJob:
    user_id: str
    image_id: str
    source: str
    api_key: str | None
    existing_products: list[dict[str, Any]]
    user_stores: list[dict[str, Any]]
    exif: dict[str, Any]
    photo_type: str
    date_folder: str
    captured_at: str | None
    store_location_id: str | None
    content_hash: str


def register_extraction_complete(callback: Callable[[str, dict[str, Any]], None]) -> None:
    _on_complete_callbacks.append(callback)


def enqueue_extraction(job: ExtractionJob, runner: Callable[[ExtractionJob], dict[str, Any]]) -> None:
    _executor.submit(_run_job, job, runner)


def _run_job(job: ExtractionJob, runner: Callable[[ExtractionJob], dict[str, Any]]) -> None:
    with _llm_semaphore:
        try:
            result = runner(job)
        except Exception as err:
            result = {
                "image_id": job.image_id,
                "extraction_status": "failed",
                "extraction_error": str(err),
            }
    for callback in _on_complete_callbacks:
        try:
            callback(job.user_id, result)
        except Exception:
            pass


def shutdown_worker() -> None:
    _executor.shutdown(wait=False)


atexit.register(shutdown_worker)
