"""Backward-compatible facade over extract_server.db users and connection."""

from __future__ import annotations

from extract_server.db import init_db
from extract_server.db.connection import DB_PATH, close_all_connections, db_path, get_conn
from extract_server.db.extractions import count_extractions
from extract_server.db.users import (
    User,
    authenticate_user,
    complete_onboarding,
    create_session,
    delete_session,
    get_user_by_id,
    get_user_extract_backend,
    get_user_id_for_session,
    register_user,
    set_user_extract_backend,
    user_needs_onboarding,
)

__all__ = [
    "DB_PATH",
    "User",
    "authenticate_user",
    "close_all_connections",
    "complete_onboarding",
    "count_user_extractions",
    "create_session",
    "delete_session",
    "get_conn",
    "get_user_by_id",
    "get_user_extract_backend",
    "get_user_id_for_session",
    "init_db",
    "register_user",
    "set_user_extract_backend",
    "user_needs_onboarding",
]


def count_user_extractions(user_id: str) -> int:
    return count_extractions(user_id)
