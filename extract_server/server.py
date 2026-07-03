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
    issue_session,
    logout_session,
    require_user,
    _bearer,
)
from fastapi import Cookie, Form, Response  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402

from grocery_extract.catalog_edit import add_product, reextract_photo, update_product  # noqa: E402
from grocery_extract.delete import delete_product, delete_products_bulk  # noqa: E402
from grocery_extract.ingest import ingest_upload, ingest_upload_batch  # noqa: E402
from grocery_extract.pipeline import extract_from_upload  # noqa: E402
from grocery_extract.photo_stores import set_image_store_location_id
from grocery_extract.products_builder import build_product_lines, write_user_products_jsonl
from grocery_extract.user_paths import find_user_jpg  # noqa: E402
from extract_server.user_stores import (  # noqa: E402
    create_user_store,
    delete_user_store,
    get_user_store,
    list_user_stores,
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
        "extractor": "cursor_sdk",
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
def auth_me(user: Annotated[AuthUser, Depends(require_user)]) -> dict:
    upload_count = count_user_extractions(user.id)
    return {
        "authenticated": True,
        "username": user.username,
        "upload_count": upload_count,
        "needs_onboarding": user_needs_onboarding(user.id),
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
    return build_product_lines(user_id=user.id)


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
    if not os.environ.get("CURSOR_API_KEY"):
        raise HTTPException(status_code=503, detail="CURSOR_API_KEY not configured")
    try:
        result = reextract_photo(user.id, image_id)
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
    return [store_to_api_dict(store) for store in list_user_stores(user.id)]


@app.post("/api/store-locations")
def create_store_location(
    body: StoreLocationBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    try:
        store = create_user_store(user.id, **body.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return store_to_api_dict(store)


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
    write_user_products_jsonl(user.id)
    return store_to_api_dict(store)


@app.delete("/api/store-locations/{store_id}")
def remove_store_location(
    store_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict[str, bool]:
    if not delete_user_store(user.id, store_id):
        raise HTTPException(status_code=404, detail="Store location not found")
    write_user_products_jsonl(user.id)
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
    write_user_products_jsonl(user.id)
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


@app.post("/extract")
async def extract(file: UploadFile = File(...)) -> JSONResponse:
    return await _extract_upload(file)


@app.post("/api/photos/upload")
async def upload_photo(
    file: UploadFile = File(...),
    duplicate_action: Annotated[str | None, Form()] = None,
    user: AuthUser = Depends(require_user),
) -> JSONResponse:
    return await _ingest_single(
        file,
        user=user,
        source="upload",
        duplicate_action=duplicate_action,
    )


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
        for upload in files:
            if not upload.filename:
                continue
            path = tmp_dir / Path(upload.filename).name
            path.write_bytes(await upload.read())
            saved_paths.append(path)

        if not saved_paths:
            raise HTTPException(status_code=400, detail="No valid files uploaded")

        if not os.environ.get("CURSOR_API_KEY"):
            raise HTTPException(status_code=503, detail="CURSOR_API_KEY not configured")

        try:
            results = await asyncio.to_thread(
                ingest_upload_batch,
                saved_paths,
                user_id=user.id,
                source=ingest_source,
                duplicate_action=duplicate_action,
            )
        except Exception as err:
            raise HTTPException(status_code=502, detail=str(err)) from err

    if any(not result.get("action_required") for result in results):
        complete_onboarding(user.id)
    return JSONResponse({"results": results, "count": len(results)})


async def _extract_upload(file: UploadFile) -> JSONResponse:
    upload_path = await _save_upload(file)
    if not os.environ.get("CURSOR_API_KEY"):
        raise HTTPException(status_code=503, detail="CURSOR_API_KEY not configured")
    try:
        result = extract_from_upload(upload_path)
    except Exception as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    return JSONResponse(result.model_dump(mode="json"))


async def _ingest_single(
    file: UploadFile,
    *,
    user: AuthUser,
    source: str,
    duplicate_action: str | None = None,
) -> JSONResponse:
    upload_path = await _save_upload(file)
    if not os.environ.get("CURSOR_API_KEY"):
        raise HTTPException(status_code=503, detail="CURSOR_API_KEY not configured")
    try:
        payload = await asyncio.to_thread(
            ingest_upload,
            upload_path,
            user_id=user.id,
            source=source,
            duplicate_action=duplicate_action,
        )
    except Exception as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    if not payload.get("action_required"):
        complete_onboarding(user.id)
    return JSONResponse(payload)


_MIME_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heic",
}


def _upload_suffix(filename: str | None, content_type: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        return suffix if suffix != ".jpeg" else ".jpg"
    if content_type:
        mime = content_type.split(";", 1)[0].strip().lower()
        if mime in _MIME_SUFFIX:
            return _MIME_SUFFIX[mime]
    return ""


async def _save_upload(file: UploadFile) -> Path:
    suffix = _upload_suffix(file.filename, file.content_type)
    if suffix not in {".jpg", ".png", ".webp", ".heic"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.filename or 'unknown'} ({file.content_type})",
        )

    tmp = tempfile.mkdtemp(prefix="grocery-upload-")
    stem = Path(file.filename or "upload").stem or "upload"
    upload_path = Path(tmp) / f"{stem}{suffix}"
    upload_path.write_bytes(await file.read())
    return upload_path


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8765, reload=False)
