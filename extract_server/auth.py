from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from extract_server.users_db import User, create_session, delete_session, get_user_by_id, get_user_id_for_session

SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
SESSION_COOKIE = "grocery_session"
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str


def _cookie_domain() -> str | None:
    domain = os.environ.get("GROCERY_COOKIE_DOMAIN", ".daliu.ca").strip()
    return domain or None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        domain=_cookie_domain(),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        domain=_cookie_domain(),
        path="/",
    )


def issue_session(response: Response, user: User) -> str:
    token = create_session(user.id, expires_at=time.time() + SESSION_TTL_SECONDS)
    set_session_cookie(response, token)
    return token


def logout_session(response: Response, token: str | None) -> None:
    if token:
        delete_session(token)
    clear_session_cookie(response)


def _token_from_request(
    credentials: HTTPAuthorizationCredentials | None,
    cookie_token: str | None,
) -> str | None:
    if credentials and credentials.credentials:
        return credentials.credentials
    return cookie_token


def resolve_auth_user(token: str | None) -> AuthUser | None:
    if not token:
        return None
    user_id = get_user_id_for_session(token, now=time.time())
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if not user:
        return None
    return AuthUser(id=user.id, username=user.username)


def require_user(
    request: Request,
    response: Response,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    grocery_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuthUser:
    token = _token_from_request(credentials, grocery_session)
    user = resolve_auth_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    grocery_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> AuthUser | None:
    token = _token_from_request(credentials, grocery_session)
    return resolve_auth_user(token)
