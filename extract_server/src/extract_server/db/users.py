from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass

import bcrypt

from extract_server.db._helpers import utc_now
from extract_server.db.connection import get_conn

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

ONBOARDING_WELCOME = "welcome"
ONBOARDING_RELATED_PRODUCTS = "related_products"
ONBOARDING_MULTI_PRODUCT_PHOTO = "multi_product_photo"
ALLOWED_ONBOARDING_KEYS = frozenset(
    {
        ONBOARDING_WELCOME,
        ONBOARDING_RELATED_PRODUCTS,
        ONBOARDING_MULTI_PRODUCT_PHOTO,
    }
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    onboarding_completed_at TEXT,
    extract_backend TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


@dataclass(frozen=True)
class User:
    id: str
    username: str


def init_users_tables() -> None:
    get_conn().executescript(_SCHEMA)


def _fetchone(sql: str, params: tuple[object, ...] = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, params).fetchone()


def _execute(sql: str, params: tuple[object, ...] = ()) -> None:
    get_conn().execute(sql, params)


def _normalize_username(username: str) -> str:
    username = username.strip()
    if EMAIL_RE.match(username):
        return username.lower()
    return username


def _is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username) or EMAIL_RE.match(username))


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _user_from_row(row: sqlite3.Row) -> User:
    return User(id=row["id"], username=row["username"])


def _fetch_onboarding_raw(user_id: str) -> str | None:
    row = _fetchone(
        "SELECT onboarding_completed_at FROM users WHERE id = ?",
        (user_id,),
    )
    if row is None:
        return None
    return row["onboarding_completed_at"]


def _parse_onboarding_raw(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    trimmed = raw.strip()
    if not trimmed:
        return {}
    if trimmed.startswith("{"):
        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        state: dict[str, str] = {}
        for key, value in parsed.items():
            if isinstance(key, str) and key in ALLOWED_ONBOARDING_KEYS and isinstance(value, str):
                state[key] = value
        return state
    return {ONBOARDING_WELCOME: trimmed}


def get_onboarding_state(user_id: str) -> dict[str, str]:
    return _parse_onboarding_raw(_fetch_onboarding_raw(user_id))


def list_onboarding_completed(user_id: str) -> list[str]:
    return sorted(get_onboarding_state(user_id).keys())


def user_needs_onboarding(user_id: str) -> bool:
    return ONBOARDING_WELCOME not in get_onboarding_state(user_id)


def complete_onboarding(user_id: str, *, key: str = ONBOARDING_WELCOME) -> None:
    if key not in ALLOWED_ONBOARDING_KEYS:
        raise ValueError(f"Unknown onboarding key: {key}")
    state = get_onboarding_state(user_id)
    state[key] = utc_now()
    _execute(
        "UPDATE users SET onboarding_completed_at = ? WHERE id = ?",
        (json.dumps(state), user_id),
    )


def register_user(username: str, password: str) -> User:
    username = _normalize_username(username)
    if not _is_valid_username(username):
        raise ValueError("Enter a valid email or username (3-32 letters, numbers, _ or -)")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    user_id = uuid.uuid4().hex
    try:
        _execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, _hash_password(password), utc_now()),
        )
    except sqlite3.IntegrityError as err:
        raise ValueError("Username already taken") from err
    return User(id=user_id, username=username)


def authenticate_user(username: str, password: str) -> User | None:
    row = _fetchone(
        "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
        (_normalize_username(username),),
    )
    if row is None or not _verify_password(password, row["password_hash"]):
        return None
    return _user_from_row(row)


def get_user_by_id(user_id: str) -> User | None:
    row = _fetchone("SELECT id, username FROM users WHERE id = ?", (user_id,))
    return _user_from_row(row) if row else None


def create_session(user_id: str, *, expires_at: float) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    _execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    return token


def delete_session(token: str) -> None:
    _execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_user_id_for_session(token: str, *, now: float) -> str | None:
    _execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
    row = _fetchone("SELECT user_id FROM sessions WHERE token = ?", (token,))
    return row["user_id"] if row else None


def get_user_extract_backend(user_id: str) -> str:
    from extract_server.extraction.cursor_extractor import (
        VALID_EXTRACT_BACKENDS,
        current_extract_backend,
    )

    row = _fetchone("SELECT extract_backend FROM users WHERE id = ?", (user_id,))
    backend = row["extract_backend"] if row else None
    if backend in VALID_EXTRACT_BACKENDS:
        return backend
    return current_extract_backend()


def set_user_extract_backend(user_id: str, backend: str) -> str:
    from extract_server.extraction.cursor_extractor import normalize_extract_backend

    normalized = normalize_extract_backend(backend)
    _execute(
        "UPDATE users SET extract_backend = ? WHERE id = ?",
        (normalized, user_id),
    )
    return normalized
