from __future__ import annotations

from extract_server.schemas.auth import (
    AuthResponse,
    CompleteOnboardingRequest,
    LoginRequest,
    RegisterRequest,
)
from extract_server.schemas.catalog import BulkDeleteProductsBody, ManualProductBody, ProductUpdateBody
from extract_server.schemas.photos import AssignPhotoStoreBody, PhotoStatusRequest, SettingsBody
from extract_server.schemas.stores import StoreLocationBody

__all__ = [
    "AssignPhotoStoreBody",
    "CompleteOnboardingRequest",
    "BulkDeleteProductsBody",
    "LoginRequest",
    "ManualProductBody",
    "PhotoStatusRequest",
    "ProductUpdateBody",
    "RegisterRequest",
    "SettingsBody",
    "StoreLocationBody",
]
