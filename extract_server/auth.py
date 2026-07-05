from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from extract_server.users_db import User, create_session, delete_session, get_user_by_id, get_user_id_for_session

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sign in required",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str


def issue_session(user: User) -> str:
    return create_session(user.id, expires_at=time.time() + SESSION_TTL_SECONDS)


def revoke_session(token: str | None) -> None:
    if token:
        delete_session(token)


def bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str | None:
    return credentials.credentials if credentials else None


def user_from_token(token: str | None) -> AuthUser | None:
    if not token:
        return None
    user_id = get_user_id_for_session(token, now=time.time())
    if not user_id or not (user := get_user_by_id(user_id)):
        return None
    return AuthUser(id=user.id, username=user.username)


def require_user(
    request: Request,
    token: Annotated[str | None, Depends(bearer_token)],
) -> AuthUser:
    user = user_from_token(token)
    if not user:
        raise _UNAUTHORIZED
    request.state.user_id = user.id
    request.state.bearer_token = token
    return user
