from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

CANONICAL_PRODUCT_FIELDS = frozenset({
    "product_name",
    "price",
    "unit",
    "unit_price",
    "category",
    "other",
})


def fold_product_fields(product: dict[str, Any]) -> dict[str, Any]:
    """Keep canonical top-level fields; move everything else into other."""
    other = dict(product["other"]) if isinstance(product.get("other"), dict) else {}
    folded: dict[str, Any] = {}
    for key, value in product.items():
        if key == "other":
            continue
        if key in CANONICAL_PRODUCT_FIELDS:
            folded[key] = value
        elif value is not None:
            other[key] = value
    if other:
        folded["other"] = other
    return folded


class ExtractedProduct(BaseModel):
    product_name: str
    price: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    category: str
    other: dict[str, Any] | None = None

    def to_product_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        other = data.get("other")
        if isinstance(other, dict) and other.get("is_special") is False:
            other = dict(other)
            other.pop("is_special", None)
            if other:
                data["other"] = other
            else:
                data.pop("other", None)
        return data


class ExtractionTiming(BaseModel):
    llm_ms: int = 0
    other_ms: int = 0
    model: str | None = None


class ExtractionResult(BaseModel):
    image_path: str
    products: list[ExtractedProduct] = Field(default_factory=list)
    photo_type: str = "shelf"
    raw_response: str | None = None
    extractor: str = "cursor_sdk"
    timing: ExtractionTiming | None = None
