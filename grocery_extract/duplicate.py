from __future__ import annotations

import hashlib
import json
from pathlib import Path

from grocery_extract.user_paths import user_meta_path


def file_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_meta_rows(user_id: str) -> list[dict]:
    path = user_meta_path(user_id)
    if not path.exists():
        return []
    with path.open() as handle:
        return json.load(handle)


def find_exact_duplicate(user_id: str, content_hash: str) -> str | None:
    for row in _load_meta_rows(user_id):
        if row.get("ContentHash") == content_hash:
            return Path(row["SourceFile"]).stem
    return None


def set_content_hash(user_id: str, image_id: str, content_hash: str) -> None:
    path = user_meta_path(user_id)
    rows = _load_meta_rows(user_id)
    for row in rows:
        if Path(row["SourceFile"]).stem == image_id:
            row["ContentHash"] = content_hash
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")
