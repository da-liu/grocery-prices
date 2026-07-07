from __future__ import annotations

import os
from pathlib import Path

_SERVER_ROOT = Path(__file__).resolve().parents[1]
ROOT = _SERVER_ROOT.parent
_DEFAULT_DATA_DIR = _SERVER_ROOT / "data"


def data_dir() -> Path:
    return Path(os.environ.get("GROCERY_DATA_DIR", str(_DEFAULT_DATA_DIR)))


# Mutable for tests that monkeypatch this attribute directly.
DATA_DIR = data_dir()


def user_root(user_id: str) -> Path:
    return data_dir() / "users" / user_id


def user_meta_path(user_id: str) -> Path:
    return user_root(user_id) / ".meta.json"


def user_extractions_dir(user_id: str) -> Path:
    return user_root(user_id) / "extractions"


def user_photos_dir(user_id: str, date_folder: str) -> Path:
    return user_root(user_id) / "photos" / date_folder


def resolve_blob_path(blob_key: str) -> Path:
    base = data_dir()
    path = base / blob_key
    if path.exists():
        return path
    legacy = ROOT / blob_key
    if legacy.exists():
        return legacy
    return path


def find_user_jpg(user_id: str, image_id: str) -> Path | None:
    from extract_server.db.photos import get_photo_blob_path

    return get_photo_blob_path(user_id, image_id)
