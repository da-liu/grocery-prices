from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA_DIR = ROOT / "extract_server" / "data"
DATA_DIR = Path(os.environ.get("GROCERY_DATA_DIR", _DEFAULT_DATA_DIR))


def user_root(user_id: str) -> Path:
    return DATA_DIR / "users" / user_id


def user_meta_path(user_id: str) -> Path:
    return user_root(user_id) / ".meta.json"


def user_extractions_dir(user_id: str) -> Path:
    return user_root(user_id) / "extractions"


def user_photos_dir(user_id: str, date_folder: str) -> Path:
    return user_root(user_id) / "photos" / date_folder


def resolve_blob_path(blob_key: str) -> Path:
    path = DATA_DIR / blob_key
    if path.exists():
        return path
    legacy = ROOT / blob_key
    if legacy.exists():
        return legacy
    return path


def find_user_jpg(user_id: str, image_id: str) -> Path | None:
    from grocery_extract.catalog_db import get_photo_blob_path

    path = get_photo_blob_path(user_id, image_id)
    if path is not None:
        return path

    photos_root = user_root(user_id) / "photos"
    if not photos_root.exists():
        return None
    for batch_dir in sorted(photos_root.glob("20*")):
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            return jpg
        webp = batch_dir / f"{image_id}.webp"
        if webp.exists():
            return webp
    return None
