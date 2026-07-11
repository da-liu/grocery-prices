from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"


def data_dir() -> Path:
    return Path(os.environ.get("GROCERY_DATA_DIR", str(_DEFAULT_DATA_DIR)))


# Mutable for tests that monkeypatch this attribute directly.
DATA_DIR = data_dir()


def user_root(user_id: str) -> Path:
    return data_dir() / "users" / user_id


def user_photos_dir(user_id: str, date_folder: str) -> Path:
    return user_root(user_id) / "photos" / date_folder


def resolve_blob_path(blob_key: str) -> Path:
    return data_dir() / blob_key
