from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedProduct(BaseModel):
    product_name: str
    product_name_zh: str | None = None
    brand: str | None = None
    price: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    unit_price_per_100g: float | None = None
    regular_price: float | None = None
    is_special: bool | None = None
    promo: str | None = None
    barcode: str | None = None
    size: str | None = None
    net_weight: float | None = None
    net_weight_lb: float | None = None
    packed_on: str | None = None
    category: str
    notes: str | None = None
    location_override: str | None = None

    def to_product_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        if self.is_special is False and "is_special" in data:
            data.pop("is_special")
        return data


class ImageMeta(BaseModel):
    image_id: str | None = None
    source_file: str | None = None
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    captured_at: str | None = None
    date_folder: str | None = None


class ExtractionResult(BaseModel):
    image_path: str
    meta: ImageMeta
    products: list[ExtractedProduct] = Field(default_factory=list)
    raw_response: str | None = None
    extractor: str = "cursor_sdk"
