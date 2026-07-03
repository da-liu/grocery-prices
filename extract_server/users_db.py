from __future__ import annotations

import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "grocery.db"
DB_PATH = Path(os.environ.get("GROCERY_DB_PATH", _DEFAULT_DB_PATH))
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _normalize_username(username: str) -> str:
    username = username.strip()
    if EMAIL_RE.match(username):
        return username.lower()
    return username


def _is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username) or EMAIL_RE.match(username))


@dataclass(frozen=True)
class User:
    id: str
    username: str


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "onboarding_completed_at" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN onboarding_completed_at TEXT")

    from grocery_extract.catalog_db import init_catalog_tables
    from grocery_extract.user_stores_db import init_user_store_tables

    init_user_store_tables()
    init_catalog_tables()


def user_needs_onboarding(user_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT onboarding_completed_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return True
    return row["onboarding_completed_at"] is None


def complete_onboarding(user_id: str) -> None:
    completed_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET onboarding_completed_at = ? WHERE id = ?",
            (completed_at, user_id),
        )


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def register_user(username: str, password: str) -> User:
    username = _normalize_username(username)
    if not _is_valid_username(username):
        raise ValueError("Enter a valid email or username (3-32 letters, numbers, _ or -)")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    user_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (user_id, username, _hash_password(password), created_at),
            )
        except sqlite3.IntegrityError as err:
            raise ValueError("Username already taken") from err
    return User(id=user_id, username=username)


def authenticate_user(username: str, password: str) -> User | None:
    username = _normalize_username(username)
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
    if row is None or not _verify_password(password, row["password_hash"]):
        return None
    return User(id=row["id"], username=row["username"])


def get_user_by_id(user_id: str) -> User | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return User(id=row["id"], username=row["username"])


def create_session(user_id: str, *, expires_at: float) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def delete_session(token: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_user_id_for_session(token: str, *, now: float) -> str | None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
    return row["user_id"] if row else None


def count_user_extractions(user_id: str) -> int:
    from grocery_extract.catalog_db import count_extractions

    return count_extractions(user_id)
