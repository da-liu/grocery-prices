from __future__ import annotations

from pydantic import BaseModel, Field


class StoreLocationBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float
    longitude: float
    match_radius_m: int = Field(default=150, ge=25, le=2000)
