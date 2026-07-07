from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "grocery.db"

_local = threading.local()
_tracked_lock = threading.Lock()
_tracked_connections: list[sqlite3.Connection] = []


def db_path() -> Path:
    return Path(os.environ.get("GROCERY_DB_PATH", str(_DEFAULT_DB_PATH)))


# Mutable for tests that monkeypatch this attribute directly.
DB_PATH = db_path()


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    path = db_path()
    if conn is None or getattr(_local, "db_path", None) != path:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            path,
            timeout=5.0,
            check_same_thread=False,
            isolation_level=None,
        )
        _configure(conn)
        _local.conn = conn
        _local.db_path = path
        with _tracked_lock:
            _tracked_connections.append(conn)
    return conn


def close_all_connections() -> None:
    with _tracked_lock:
        for conn in _tracked_connections:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        _tracked_connections.clear()
    if hasattr(_local, "conn"):
        del _local.conn
    if hasattr(_local, "db_path"):
        del _local.db_path
