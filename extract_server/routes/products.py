from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from extract_server.auth import AuthUser, require_user
from extract_server.schemas import BulkDeleteProductsBody, ProductUpdateBody
from extract_server.db import add_product, is_valid_photo_id, list_product_rows, reextract_photo, update_product
from extract_server.grocery_extract.delete import delete_product, delete_products_bulk

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
def list_products(user: Annotated[AuthUser, Depends(require_user)]) -> list[dict]:
    return list_product_rows(user.id)


@router.patch("/{product_id}")
def patch_product(
    product_id: str,
    body: ProductUpdateBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = update_product(user.id, product_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated


@router.delete("/{product_id}")
def remove_product(
    product_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict[str, bool]:
    if not delete_product(user.id, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@router.post("/bulk-delete")
def remove_products_bulk(
    body: BulkDeleteProductsBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    result = delete_products_bulk(user.id, body.ids)
    if result["deleted"] == 0 and result["failed"]:
        raise HTTPException(status_code=404, detail="No products deleted")
    return result
