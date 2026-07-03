from __future__ import annotations

import hashlib
from pathlib import Path

from grocery_extract.catalog_db import find_photo_by_content_hash


def file_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_exact_duplicate(user_id: str, content_hash: str) -> str | None:
    return find_photo_by_content_hash(user_id, content_hash)
