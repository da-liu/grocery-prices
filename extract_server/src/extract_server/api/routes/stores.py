from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from extract_server.api.dependencies import AuthUser, require_user
from extract_server.schemas import StoreLocationBody
from extract_server.db import (
    count_photos_for_store,
    create_user_store,
    delete_user_store,
    list_user_stores,
    store_to_api_dict,
    update_user_store,
)

router = APIRouter(prefix="/api/store-locations", tags=["stores"])


def _store_payload(user_id: str, store) -> dict:
    return store_to_api_dict(store, photo_count=count_photos_for_store(user_id, store.id))


@router.get("")
def list_store_locations(user: Annotated[AuthUser, Depends(require_user)]) -> list[dict]:
    return [_store_payload(user.id, store) for store in list_user_stores(user.id)]


@router.post("")
def create_store_location(
    body: StoreLocationBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    try:
        result = create_user_store(user.id, **body.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return {
        **_store_payload(user.id, result.store),
        "matched_existing": result.matched_existing,
    }


@router.put("/{store_id}")
def update_store_location(
    store_id: str,
    body: StoreLocationBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    try:
        store = update_user_store(user.id, store_id, **body.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if store is None:
        raise HTTPException(status_code=404, detail="Store location not found")
    return store_to_api_dict(store)


@router.delete("/{store_id}")
def remove_store_location(
    store_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict[str, bool]:
    if not delete_user_store(user.id, store_id):
        raise HTTPException(status_code=404, detail="Store location not found")
    return {"ok": True}
