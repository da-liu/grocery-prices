from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from extract_server.auth import (
    AuthUser,
    bearer_token,
    issue_session,
    require_user,
    revoke_session,
)
from extract_server.schemas import AuthResponse, LoginRequest, RegisterRequest
from extract_server.users_db import (
    authenticate_user,
    complete_onboarding,
    count_user_extractions,
    register_user,
    user_needs_onboarding,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_payload(user) -> AuthResponse:
    return AuthResponse(
        token=issue_session(user),
        username=user.username,
        upload_count=count_user_extractions(user.id),
        needs_onboarding=user_needs_onboarding(user.id),
    )


@router.post("/register")
def register(body: RegisterRequest) -> AuthResponse:
    try:
        user = register_user(body.username, body.password)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return _auth_payload(user)


@router.post("/login")
def login(body: LoginRequest) -> AuthResponse:
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _auth_payload(user)


@router.post("/logout")
def logout(token: Annotated[str | None, Depends(bearer_token)]) -> dict[str, bool]:
    revoke_session(token)
    return {"ok": True}


@router.get("/me")
def auth_me(
    request: Request,
    user: Annotated[AuthUser, Depends(require_user)],
) -> dict:
    return {
        "authenticated": True,
        "username": user.username,
        "upload_count": count_user_extractions(user.id),
        "needs_onboarding": user_needs_onboarding(user.id),
        "token": request.state.bearer_token,
    }


@router.post("/onboarding/complete")
def finish_onboarding(user: Annotated[AuthUser, Depends(require_user)]) -> dict:
    complete_onboarding(user.id)
    return {"ok": True, "needs_onboarding": False}
