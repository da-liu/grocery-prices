from __future__ import annotations

from pydantic import BaseModel, Field


class AssignPhotoStoreBody(BaseModel):
    store_location_id: str


class PhotoStatusRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
