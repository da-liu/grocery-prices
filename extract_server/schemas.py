from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str
    upload_count: int
    needs_onboarding: bool


class StoreLocationBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float
    longitude: float
    match_radius_m: int = Field(default=150, ge=25, le=2000)


class AssignPhotoStoreBody(BaseModel):
    store_location_id: str


class BulkDeleteProductsBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


class ProductUpdateBody(BaseModel):
    product_name: str | None = None
    other: dict[str, Any] | None = None
    price: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    category: str | None = None


class ManualProductBody(BaseModel):
    product_name: str = Field(min_length=1)
    other: dict[str, Any] | None = None
    price: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    category: str = "pantry"


class SettingsBody(BaseModel):
    extract_backend: str = Field(min_length=1, max_length=32)


class PhotoStatusRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
