from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from extract_server.auth import AuthUser, require_user
from extract_server.extract_config import set_user_extract_backend, settings_payload
from extract_server.schemas import SettingsBody

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(user: Annotated[AuthUser, Depends(require_user)]) -> dict:
    return settings_payload(user.id)


@router.patch("")
def update_settings(
    body: SettingsBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    try:
        set_user_extract_backend(user.id, body.extract_backend)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return settings_payload(user.id)
