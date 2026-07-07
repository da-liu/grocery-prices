from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from extract_server.core.exceptions import ConfigError, ExtractionError, GroceryError
from extract_server.core.request import request_id_from_request, request_id_header

logger = logging.getLogger("grocery_api")


def _json_error(request: Request, status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=request_id_header(request),
    )


def _log_exception(
    request: Request,
    event: str,
    *,
    level: int = logging.ERROR,
    exc_info: bool = True,
) -> None:
    logger.log(
        level,
        "%s method=%s path=%s request_id=%s",
        event,
        request.method,
        request.url.path,
        request_id_from_request(request),
        exc_info=exc_info,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        level = logging.WARNING if exc.status_code < 500 else logging.ERROR
        logger.log(
            level,
            "http_error method=%s path=%s status=%s detail=%s request_id=%s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.detail,
            request_id_from_request(request),
        )
        headers = dict(exc.headers or {})
        headers.update(request_id_header(request))
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )

    @app.exception_handler(ConfigError)
    async def config_error_handler(request: Request, exc: ConfigError) -> JSONResponse:
        _log_exception(
            request,
            f"config_error message={exc}",
            exc_info=False,
        )
        return _json_error(request, 503, "Extraction unavailable")

    @app.exception_handler(ExtractionError)
    async def extraction_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
        _log_exception(request, "extraction_error")
        return _json_error(request, 502, "Extraction failed")

    @app.exception_handler(GroceryError)
    async def grocery_error_handler(request: Request, exc: GroceryError) -> JSONResponse:
        _log_exception(request, "grocery_error")
        return _json_error(request, 502, "Request failed")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _log_exception(request, "unhandled_error")
        return _json_error(request, 500, "Internal server error")
