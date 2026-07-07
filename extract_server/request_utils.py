from __future__ import annotations

from fastapi import Request

from grocery_extract.request_context import get_request_id


def request_id_from_request(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id() or "-"


def request_id_header(request: Request) -> dict[str, str]:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    return {"X-Request-ID": request_id} if request_id else {}
