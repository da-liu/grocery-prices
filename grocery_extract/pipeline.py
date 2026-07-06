from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from grocery_extract.cursor_extractor import current_extractor_name, extract_products_from_image
from grocery_extract.exif import (
    captured_at_from_exif,
    date_folder_from_exif,
)
from grocery_extract.schema import ExtractionResult, ExtractedProduct, ExtractionTiming, ImageMeta

ROOT = Path(__file__).resolve().parents[1]


def _resolve_jpg_path(upload_path: Path, work_dir: Path) -> Path:
    suffix = upload_path.suffix.lower()
    if suffix in {".heic", ".heif"}:
        raise ValueError(f"Unsupported image type: {suffix}")
    if suffix in {".jpg", ".jpeg", ".webp"}:
        dest = work_dir / upload_path.name
        shutil.copy2(upload_path, dest)
        return dest
    raise ValueError(f"Unsupported image type: {suffix}")


def find_image_path(image_id: str, date_folder: str | None) -> str:
    data_dir = ROOT / "data"
    if date_folder:
        rel = f"data/{date_folder}/jpg/{image_id}.jpg"
        if (data_dir / date_folder / "jpg" / f"{image_id}.jpg").exists():
            return rel
    for batch_dir in sorted(data_dir.glob("20*")):
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            return f"data/{batch_dir.name}/jpg/{image_id}.jpg"
    if date_folder:
        return f"data/{date_folder}/jpg/{image_id}.jpg"
    return f"data/jpg/{image_id}.jpg"


def extract_from_upload(
    upload_path: Path,
    *,
    image_id: str | None = None,
    api_key: str | None = None,
    prompt_variant: str = "shelf",
    exif: dict[str, Any] | None = None,
    skip_normalize: bool = False,
) -> ExtractionResult:
    """Full pipeline: normalize image and extract products via the configured backend."""
    stem = image_id or upload_path.stem
    suffix = upload_path.suffix.lower()

    if skip_normalize and suffix in {".jpg", ".jpeg", ".webp"}:
        jpg_path = upload_path
        meta_exif = exif or {}
    else:
        with tempfile.TemporaryDirectory(prefix="grocery-extract-") as tmp:
            work_dir = Path(tmp)
            jpg_path = _resolve_jpg_path(upload_path, work_dir)
            meta_exif = exif or {}
            raw_dt = meta_exif.get("DateTimeOriginal")
            date_folder = date_folder_from_exif(raw_dt)
            meta = ImageMeta(
                image_id=stem,
                source_file=str(upload_path),
                gps_latitude=meta_exif.get("GPSLatitude"),
                gps_longitude=meta_exif.get("GPSLongitude"),
                captured_at=captured_at_from_exif(raw_dt),
                date_folder=date_folder,
            )
            products_result = extract_products_from_image(
                jpg_path,
                api_key=api_key,
                prompt_variant=prompt_variant,
            )
            return ExtractionResult(
                image_path=find_image_path(stem, date_folder) if (ROOT / "data").exists() else str(jpg_path),
                meta=meta,
                products=products_result.products,
                raw_response=products_result.raw_response,
                extractor=current_extractor_name(),
                timing=ExtractionTiming(
                    prep_ms=products_result.prep_ms,
                    llm_ms=products_result.llm_ms,
                    duration_ms=products_result.prep_ms + products_result.llm_ms,
                    model=products_result.model,
                ),
            )

    raw_dt = meta_exif.get("DateTimeOriginal")
    date_folder = date_folder_from_exif(raw_dt)
    meta = ImageMeta(
        image_id=stem,
        source_file=str(upload_path),
        gps_latitude=meta_exif.get("GPSLatitude"),
        gps_longitude=meta_exif.get("GPSLongitude"),
        captured_at=captured_at_from_exif(raw_dt),
        date_folder=date_folder,
    )
    products_result = extract_products_from_image(
        jpg_path,
        api_key=api_key,
        prompt_variant=prompt_variant,
    )
    return ExtractionResult(
        image_path=find_image_path(stem, date_folder) if (ROOT / "data").exists() else str(jpg_path),
        meta=meta,
        products=products_result.products,
        raw_response=products_result.raw_response,
        extractor=current_extractor_name(),
        timing=ExtractionTiming(
            prep_ms=products_result.prep_ms,
            llm_ms=products_result.llm_ms,
            duration_ms=products_result.prep_ms + products_result.llm_ms,
            model=products_result.model,
        ),
    )


def extract_from_existing_jpg(jpg_path: Path, *, api_key: str | None = None) -> list[ExtractedProduct]:
    return extract_products_from_image(jpg_path, api_key=api_key).products
