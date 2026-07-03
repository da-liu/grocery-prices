from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DATA_DIR = ROOT / "data"
DATA_DIR = Path(os.environ.get("GROCERY_DATA_DIR", _DEFAULT_DATA_DIR))
USERS_DIR = DATA_DIR / "users"


def user_root(user_id: str) -> Path:
    return USERS_DIR / user_id


def user_meta_path(user_id: str) -> Path:
    return user_root(user_id) / ".meta.json"


def user_extractions_dir(user_id: str) -> Path:
    return user_root(user_id) / "extractions"


def user_photos_dir(user_id: str, date_folder: str) -> Path:
    return user_root(user_id) / "photos" / date_folder


def user_products_path(user_id: str) -> Path:
    return user_root(user_id) / "products.jsonl"


def find_user_jpg(user_id: str, image_id: str) -> Path | None:
    photos_root = user_root(user_id) / "photos"
    if not photos_root.exists():
        return None
    for batch_dir in sorted(photos_root.glob("20*")):
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            return jpg
    return None
