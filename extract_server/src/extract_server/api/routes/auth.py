from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from extract_server.api.dependencies import (
    AuthUser,
    bearer_token,
    issue_session,
    require_user,
    revoke_session,
)
from extract_server.schemas import (
    AuthResponse,
    CompleteOnboardingRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
)
from extract_server.db import (
    authenticate_user,
    complete_onboarding,
    count_extractions,
    list_onboarding_completed,
    register_user,
    remove_registered_user,
    verify_user_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_payload(user) -> AuthResponse:
    return AuthResponse(
        token=issue_session(user),
        username=user.username,
        upload_count=count_extractions(user.id),
        onboarding_completed=list_onboarding_completed(user.id),
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
        "upload_count": count_extractions(user.id),
        "onboarding_completed": list_onboarding_completed(user.id),
        "token": request.state.bearer_token,
    }


@router.post("/onboarding/complete")
def complete_onboarding_route(
    user: Annotated[AuthUser, Depends(require_user)],
    body: CompleteOnboardingRequest | None = None,
) -> dict:
    key = body.key if body else "welcome"
    try:
        complete_onboarding(user.id, key=key)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return {
        "onboarding_completed": list_onboarding_completed(user.id),
    }


@router.delete("/account")
def delete_account(
    user: Annotated[AuthUser, Depends(require_user)],
    body: DeleteAccountRequest,
) -> Response:
    if not verify_user_password(user.id, body.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    if not remove_registered_user(user.id):
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=204)
