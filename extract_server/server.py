from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extract_server.auth import (  # noqa: E402
    AuthUser,
    get_request_session_token,
    issue_session,
    logout_session,
    require_user,
    _bearer,
)
from fastapi import Cookie, Form, Response  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402

from grocery_extract.catalog_edit import add_product, reextract_photo, update_product  # noqa: E402
from grocery_extract.catalog_db import list_product_rows
from grocery_extract.cursor_extractor import CursorExtractError, configured_api_key  # noqa: E402
from grocery_extract.delete import delete_product, delete_products_bulk  # noqa: E402
from grocery_extract.ingest import accept_upload_batch, build_status_response  # noqa: E402
from grocery_extract.photo_stores import set_image_store_location_id
from grocery_extract.user_paths import find_user_jpg  # noqa: E402
from grocery_extract.user_stores_db import (  # noqa: E402
    count_photos_for_store,
    create_user_store,
    delete_user_store,
    get_user_store,
    list_user_stores,
    merge_user_stores,
    store_to_api_dict,
    update_user_store,
)
from extract_server.users_db import (  # noqa: E402
    authenticate_user,
    complete_onboarding,
    count_user_extractions,
    init_db,
    register_user,
    user_needs_onboarding,
)

init_db()

app = FastAPI(title="Grocery Price API", version="3.0.0")

_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "GROCERY_CORS_ORIGINS",
        "https://g.daliu.ca,http://localhost:41873",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    maps_url: str | None = None


class AssignPhotoStoreBody(BaseModel):
    store_location_id: str


class MergeStoreLocationsBody(BaseModel):
    source_id: str
    target_id: str


class BulkDeleteProductsBody(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


class ProductUpdateBody(BaseModel):
    product_name: str | None = None
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
    category: str | None = None
    notes: str | None = None


class ManualProductBody(BaseModel):
    product_name: str = Field(min_length=1)
    product_name_zh: str | None = None
    brand: str | None = None
    price: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    barcode: str | None = None
    size: str | None = None
    category: str = "pantry"
    notes: str | None = None


def _auth_payload(response: Response, user) -> AuthResponse:
    token = issue_session(response, user)
    upload_count = count_user_extractions(user.id)
    return AuthResponse(
        token=token,
        username=user.username,
        upload_count=upload_count,
        needs_onboarding=user_needs_onboarding(user.id),
    )


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "auth_required": True,
    }


@app.post("/api/auth/register")
def register(body: RegisterRequest, response: Response) -> AuthResponse:
    try:
        user = register_user(body.username, body.password)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return _auth_payload(response, user)


@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response) -> AuthResponse:
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _auth_payload(response, user)


@app.post("/api/auth/logout")
def logout(
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    grocery_session: Annotated[str | None, Cookie(alias="grocery_session")] = None,
) -> dict[str, bool]:
    token = credentials.credentials if credentials else grocery_session
    logout_session(response, token)
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(
    user: Annotated[AuthUser, Depends(require_user)],
    token: Annotated[str | None, Depends(get_request_session_token)],
) -> dict:
    upload_count = count_user_extractions(user.id)
    return {
        "authenticated": True,
        "username": user.username,
        "upload_count": upload_count,
        "needs_onboarding": user_needs_onboarding(user.id),
        "token": token,
    }


@app.post("/api/auth/onboarding/complete")
def finish_onboarding(user: Annotated[AuthUser, Depends(require_user)]) -> dict:
    complete_onboarding(user.id)
    return {
        "ok": True,
        "needs_onboarding": False,
    }


@app.get("/api/products")
def list_products(user: Annotated[AuthUser, Depends(require_user)]) -> list[dict]:
    return list_product_rows(user.id)


@app.patch("/api/products/{product_id}")
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


@app.post("/api/photos/{image_id}/products")
def create_manual_product(
    image_id: str,
    body: ManualProductBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    if not image_id.startswith("IMG_"):
        raise HTTPException(status_code=400, detail="Invalid image id")
    created = add_product(user.id, image_id, body.model_dump(exclude_unset=True))
    if created is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return created


@app.post("/api/photos/{image_id}/re-extract")
def rerun_extraction(
    image_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    if not image_id.startswith("IMG_"):
        raise HTTPException(status_code=400, detail="Invalid image id")
    try:
        api_key = configured_api_key()
    except CursorExtractError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err
    try:
        result = reextract_photo(user.id, image_id, api_key=api_key)
    except Exception as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    if result is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return result


@app.delete("/api/products/{product_id}")
def remove_product(
    product_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict[str, bool]:
    if not delete_product(user.id, product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


@app.post("/api/products/bulk-delete")
def remove_products_bulk(
    body: BulkDeleteProductsBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    result = delete_products_bulk(user.id, body.ids)
    if result["deleted"] == 0 and result["failed"]:
        raise HTTPException(status_code=404, detail="No products deleted")
    return result


@app.get("/api/store-locations")
def list_store_locations(user: Annotated[AuthUser, Depends(require_user)]) -> list[dict]:
    return [
        store_to_api_dict(
            store,
            photo_count=count_photos_for_store(user.id, store.id),
        )
        for store in list_user_stores(user.id)
    ]


@app.post("/api/store-locations")
def create_store_location(
    body: StoreLocationBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    try:
        result = create_user_store(user.id, **body.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return {
        **store_to_api_dict(
            result.store,
            photo_count=count_photos_for_store(user.id, result.store.id),
        ),
        "matched_existing": result.matched_existing,
    }


@app.post("/api/store-locations/merge")
def merge_store_locations(
    body: MergeStoreLocationsBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    try:
        merged = merge_user_stores(user.id, body.source_id, body.target_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    if merged is None:
        raise HTTPException(status_code=404, detail="Store location not found")
    return store_to_api_dict(
        merged,
        photo_count=count_photos_for_store(user.id, merged.id),
    )


@app.put("/api/store-locations/{store_id}")
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


@app.delete("/api/store-locations/{store_id}")
def remove_store_location(
    store_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict[str, bool]:
    if not delete_user_store(user.id, store_id):
        raise HTTPException(status_code=404, detail="Store location not found")
    return {"ok": True}


@app.put("/api/photos/{image_id}/store-location")
def assign_photo_store(
    image_id: str,
    body: AssignPhotoStoreBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    if not image_id.startswith("IMG_"):
        raise HTTPException(status_code=400, detail="Invalid image id")
    if get_user_store(user.id, body.store_location_id) is None:
        raise HTTPException(status_code=404, detail="Store location not found")
    if not set_image_store_location_id(user.id, image_id, body.store_location_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"ok": True, "image_id": image_id, "store_location_id": body.store_location_id}


@app.get("/api/media/{image_id}")
def get_media(
    image_id: str,
    access_token: str | None = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    grocery_session: Annotated[str | None, Cookie(alias="grocery_session")] = None,
) -> FileResponse:
    from extract_server.auth import _token_from_request, resolve_auth_user

    if not image_id.startswith("IMG_"):
        raise HTTPException(status_code=400, detail="Invalid image id")
    token = access_token or _token_from_request(credentials, grocery_session)
    user = resolve_auth_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    jpg = find_user_jpg(user.id, image_id)
    if jpg is None or not jpg.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(jpg, media_type="image/jpeg")


class PhotoStatusRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


@app.get("/api/photos/status")
def photos_status_get(
    ids: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    image_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if not image_ids:
        raise HTTPException(status_code=400, detail="No image ids provided")
    return {"results": build_status_response(user.id, image_ids)}


@app.post("/api/photos/status")
def photos_status_post(
    body: PhotoStatusRequest,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    return {"results": build_status_response(user.id, body.ids)}


@app.post("/api/photos/bulk")
async def upload_photos_bulk(
    files: list[UploadFile] = File(...),
    source: Annotated[str, Form()] = "receipt",
    duplicate_action: Annotated[str | None, Form()] = None,
    user: AuthUser = Depends(require_user),
) -> JSONResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    ingest_source = "receipt" if source == "receipt" else "upload"

    saved_paths: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="grocery-bulk-") as tmp:
        tmp_dir = Path(tmp)
        for index, upload in enumerate(files):
            if not upload.filename:
                continue
            # Prefix index so same-named mobile uploads do not overwrite each other.
            path = tmp_dir / f"{index:04d}-{Path(upload.filename).name}"
            path.write_bytes(await upload.read())
            saved_paths.append(path)

        if not saved_paths:
            raise HTTPException(status_code=400, detail="No valid files uploaded")

        try:
            api_key = configured_api_key()
        except CursorExtractError as err:
            raise HTTPException(status_code=503, detail=str(err)) from err

        try:
            results = await asyncio.to_thread(
                accept_upload_batch,
                saved_paths,
                user_id=user.id,
                source=ingest_source,
                duplicate_action=duplicate_action,
                api_key=api_key,
                enqueue=True,
            )
        except Exception as err:
            raise HTTPException(status_code=502, detail=str(err)) from err

    if any(not result.get("action_required") for result in results):
        complete_onboarding(user.id)
    return JSONResponse({"results": results, "count": len(results)}, status_code=202)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=False)
