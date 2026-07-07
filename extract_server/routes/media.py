from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from extract_server.auth import bearer_token, user_from_token
from extract_server.db import is_valid_photo_id
from extract_server.grocery_extract.user_paths import find_user_jpg

router = APIRouter(prefix="/api/media", tags=["media"])

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@router.get("/{image_id}")
def get_media(
    image_id: str,
    header_token: Annotated[str | None, Depends(bearer_token)],
    access_token: str | None = None,
) -> FileResponse:
    if not is_valid_photo_id(image_id):
        raise HTTPException(status_code=400, detail="Invalid image id")
    user = user_from_token(access_token or header_token)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    image_path = find_user_jpg(user.id, image_id)
    if image_path is None or not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    media_type = _MEDIA_TYPES.get(image_path.suffix.lower(), "application/octet-stream")
    return FileResponse(image_path, media_type=media_type)
