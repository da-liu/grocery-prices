from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from extract_server.auth import AuthUser, require_user
from extract_server.extract_config import user_extract_credentials
from extract_server.request_utils import request_id_from_request
from extract_server.schemas import AssignPhotoStoreBody, ManualProductBody, PhotoStatusRequest
from extract_server.users_db import complete_onboarding
from extract_server.db import add_product, get_user_store, is_valid_photo_id, reextract_photo
from extract_server.grocery_extract.ingest import accept_upload_batch, build_status_response
from extract_server.grocery_extract.photo_stores import set_image_store_location_id

router = APIRouter(prefix="/api/photos", tags=["photos"])


def _require_valid_photo_id(image_id: str) -> None:
    if not is_valid_photo_id(image_id):
        raise HTTPException(status_code=400, detail="Invalid image id")


@router.get("/status")
def photos_status_get(
    ids: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    image_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if not image_ids:
        raise HTTPException(status_code=400, detail="No image ids provided")
    return {"results": build_status_response(user.id, image_ids)}


@router.post("/status")
def photos_status_post(
    body: PhotoStatusRequest,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    return {"results": build_status_response(user.id, body.ids)}


@router.post("/bulk")
async def upload_photos_bulk(
    request: Request,
    files: list[UploadFile] = File(...),
    duplicate_action: Annotated[str | None, Form()] = None,
    exif_json: Annotated[str | None, Form()] = None,
    user: AuthUser = Depends(require_user),
) -> JSONResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    client_exifs = _parse_exif_json(exif_json, len(files))
    extract_backend, api_key = user_extract_credentials(user.id)

    with tempfile.TemporaryDirectory(prefix="grocery-bulk-") as tmp:
        saved_paths = await _save_uploads(Path(tmp), files)
        try:
            results = await asyncio.to_thread(
                accept_upload_batch,
                saved_paths,
                user_id=user.id,
                duplicate_action=duplicate_action,
                api_key=api_key,
                enqueue=True,
                client_exifs=client_exifs,
                request_id=request_id_from_request(request),
                extract_backend=extract_backend,
            )
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    if any(not result.get("action_required") for result in results):
        complete_onboarding(user.id)
    return JSONResponse({"results": results, "count": len(results)}, status_code=202)


@router.post("/{image_id}/products")
def create_manual_product(
    image_id: str,
    body: ManualProductBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    _require_valid_photo_id(image_id)
    created = add_product(user.id, image_id, body.model_dump(exclude_unset=True))
    if created is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return created


@router.post("/{image_id}/re-extract")
def rerun_extraction(
    image_id: str,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    _require_valid_photo_id(image_id)
    extract_backend, api_key = user_extract_credentials(user.id)
    result = reextract_photo(
        user.id,
        image_id,
        api_key=api_key,
        extract_backend=extract_backend,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return result


@router.put("/{image_id}/store-location")
def assign_photo_store(
    image_id: str,
    body: AssignPhotoStoreBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    _require_valid_photo_id(image_id)
    if get_user_store(user.id, body.store_location_id) is None:
        raise HTTPException(status_code=404, detail="Store location not found")
    if not set_image_store_location_id(user.id, image_id, body.store_location_id):
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"ok": True, "image_id": image_id, "store_location_id": body.store_location_id}


def _parse_exif_json(exif_json: str | None, file_count: int) -> list[dict | None] | None:
    if not exif_json:
        return None
    try:
        parsed = json.loads(exif_json)
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=400, detail="Invalid exif_json") from err
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="exif_json must be a JSON array")
    if len(parsed) != file_count:
        raise HTTPException(
            status_code=400,
            detail="exif_json length must match number of uploaded files",
        )
    return parsed


async def _save_uploads(tmp_dir: Path, files: list[UploadFile]) -> list[Path]:
    saved_paths: list[Path] = []
    for index, upload in enumerate(files):
        if not upload.filename:
            continue
        path = tmp_dir / f"{index:04d}-{Path(upload.filename).name}"
        path.write_bytes(await upload.read())
        saved_paths.append(path)
    if not saved_paths:
        raise HTTPException(status_code=400, detail="No valid files uploaded")
    return saved_paths
