from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
