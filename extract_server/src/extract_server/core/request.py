from __future__ import annotations

import contextvars

from fastapi import Request

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id.reset(token)


def request_id_from_request(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id() or "-"


def request_id_header(request: Request) -> dict[str, str]:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    return {"X-Request-ID": request_id} if request_id else {}
