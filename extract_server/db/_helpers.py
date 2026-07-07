from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

TORONTO = ZoneInfo("America/Toronto")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def toronto_now() -> str:
    return datetime.now(TORONTO).isoformat(timespec="seconds")


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row["count"]) if row else 0
