from __future__ import annotations

import re
import uuid

PHOTO_ID_RE = re.compile(r"^(?:[a-f0-9]{32}|IMG_\d+)$")
EMPTY_SIGHTING_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def is_valid_photo_id(photo_id: str) -> bool:
    return bool(PHOTO_ID_RE.match(photo_id))


def new_photo_id() -> str:
    return uuid.uuid4().hex


def new_photo_ids(count: int) -> list[str]:
    if count <= 0:
        return []
    return [new_photo_id() for _ in range(count)]


def empty_sighting_id(user_id: str, photo_id: str) -> str:
    return uuid.uuid5(EMPTY_SIGHTING_NS, f"{user_id}/{photo_id}/empty").hex


def blob_key(user_id: str, date_folder: str, image_id: str) -> str:
    return f"users/{user_id}/photos/{date_folder}/{image_id}.webp"
