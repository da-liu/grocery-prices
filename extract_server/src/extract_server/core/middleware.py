from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from extract_server.core.request import get_request_id, reset_request_id, set_request_id

logger = logging.getLogger("grocery_api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        token = set_request_id(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            user_id = getattr(request.state, "user_id", None)
            logger.info(
                "request_complete method=%s path=%s status=%s duration_ms=%s request_id=%s user_id=%s",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                get_request_id() or request_id,
                user_id or "-",
            )
            reset_request_id(token)
