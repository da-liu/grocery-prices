from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from grocery_extract.cursor_extractor import extract_products_from_image
from grocery_extract.exif import (
    captured_at_from_exif,
    convert_heic_to_jpg,
    date_folder_from_exif,
    extract_exif,
)
from grocery_extract.schema import ExtractionResult, ExtractedProduct, ImageMeta

ROOT = Path(__file__).resolve().parents[1]


def _resolve_jpg_path(upload_path: Path, work_dir: Path) -> Path:
    suffix = upload_path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        dest = work_dir / upload_path.name
        shutil.copy2(upload_path, dest)
        return dest
    if suffix == ".heic":
        jpg_path = work_dir / f"{upload_path.stem}.jpg"
        convert_heic_to_jpg(upload_path, jpg_path)
        return jpg_path
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
) -> ExtractionResult:
    """Full pipeline: normalize image, read EXIF, extract products via Cursor SDK."""
    with tempfile.TemporaryDirectory(prefix="grocery-extract-") as tmp:
        work_dir = Path(tmp)
        jpg_path = _resolve_jpg_path(upload_path, work_dir)

        exif_source = upload_path if upload_path.suffix.lower() == ".heic" else jpg_path
        exif = extract_exif(exif_source) if exif_source.exists() else {}

        stem = image_id or upload_path.stem
        raw_dt = exif.get("DateTimeOriginal")
        date_folder = date_folder_from_exif(raw_dt)

        meta = ImageMeta(
            image_id=stem,
            source_file=str(upload_path),
            gps_latitude=exif.get("GPSLatitude"),
            gps_longitude=exif.get("GPSLongitude"),
            captured_at=captured_at_from_exif(raw_dt),
            date_folder=date_folder,
        )

        products, raw = extract_products_from_image(
            jpg_path,
            api_key=api_key,
            prompt_variant=prompt_variant,
        )

        return ExtractionResult(
            image_path=find_image_path(stem, date_folder) if (ROOT / "data").exists() else str(jpg_path),
            meta=meta,
            products=products,
            raw_response=raw,
            extractor="cursor_sdk",
        )


def extract_from_existing_jpg(jpg_path: Path, *, api_key: str | None = None) -> list[ExtractedProduct]:
    products, _ = extract_products_from_image(jpg_path, api_key=api_key)
    return products
