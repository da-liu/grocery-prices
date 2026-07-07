from __future__ import annotations

from extract_server.db import get_user_extract_backend, set_user_extract_backend
from extract_server.extraction.cursor_extractor import configured_api_key, default_extract_model


def settings_payload(user_id: str) -> dict[str, str]:
    backend = get_user_extract_backend(user_id)
    return {
        "extract_backend": backend,
        "extract_model": default_extract_model(backend),
    }


def user_extract_credentials(user_id: str) -> tuple[str, str]:
    backend = get_user_extract_backend(user_id)
    return backend, configured_api_key(backend=backend)


__all__ = [
    "settings_payload",
    "set_user_extract_backend",
    "user_extract_credentials",
]
