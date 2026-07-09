from __future__ import annotations

import sqlite3
from typing import Any

from extract_server.db._helpers import one, toronto_now, utc_now
from extract_server.db.connection import get_conn
from extract_server.db.photos import set_photo_type

_EXTRACTION_TIMING_SET = (
    "llm_ms = ?, other_ms = ?, model = ?, product_count = ?, extraction_error = NULL, status = ?"
)

_PIPELINE_STATUSES = frozenset({"extracted", "matched", "failed", "match_failed"})


def _ensure_extractions_status_column(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(extractions)").fetchall()}
    if "status" not in columns:
        conn.execute("ALTER TABLE extractions ADD COLUMN status TEXT")


def init_extractions_table() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS extractions (
            user_id TEXT NOT NULL,
            photo_id TEXT NOT NULL,
            extractor TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            reextracted_at TEXT,
            manually_edited_at TEXT,
            raw_response TEXT,
            llm_ms INTEGER,
            other_ms INTEGER,
            model TEXT,
            product_count INTEGER,
            extraction_error TEXT,
            status TEXT,
            PRIMARY KEY (user_id, photo_id),
            FOREIGN KEY (user_id, photo_id) REFERENCES photos(user_id, id) ON DELETE CASCADE
        )
        """
    )
    _ensure_extractions_status_column(conn)


def extraction_timing_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("llm_ms") is None and row.get("other_ms") is None:
        return None
    payload = {
        "llm_ms": row.get("llm_ms"),
        "other_ms": row.get("other_ms"),
        "model": row.get("model"),
    }
    return {key: value for key, value in payload.items() if value is not None}


def count_extractions(user_id: str) -> int:
    from extract_server.db._helpers import count

    conn = get_conn()
    return count(conn, "SELECT COUNT(*) AS count FROM extractions WHERE user_id = ?", (user_id,))


def record_photo_extraction_failure(user_id: str, photo_id: str, error: str) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO extractions (
            user_id, photo_id, extractor, extracted_at, extraction_error, product_count, status
        ) VALUES (?, ?, '_failed', ?, ?, 0, 'failed')
        ON CONFLICT(user_id, photo_id) DO UPDATE SET
            extractor = excluded.extractor,
            extracted_at = excluded.extracted_at,
            extraction_error = excluded.extraction_error,
            product_count = 0,
            status = 'failed'
        """,
        (user_id, photo_id, toronto_now(), error),
    )


def get_extraction(user_id: str, photo_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    return one(
        conn,
        """
        SELECT user_id, photo_id, extractor, extracted_at, reextracted_at,
               manually_edited_at, raw_response, llm_ms, other_ms, model,
               product_count, extraction_error, status
        FROM extractions
        WHERE user_id = ? AND photo_id = ?
        """,
        (user_id, photo_id),
    )


def _write_extraction(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    photo_id: str,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    llm_ms: int | None,
    other_ms: int | None,
    model: str | None,
    replace: bool,
    reextracted: bool,
) -> None:
    extracted_at = toronto_now()
    pipeline_status = "matched" if len(products) == 0 else "extracted"
    timing = (llm_ms, other_ms, model, len(products), pipeline_status)
    if replace:
        if reextracted:
            conn.execute(
                f"""
                UPDATE extractions
                SET extractor = ?, extracted_at = ?, reextracted_at = ?,
                    raw_response = ?, {_EXTRACTION_TIMING_SET}
                WHERE user_id = ? AND photo_id = ?
                """,
                (extractor, extracted_at, extracted_at, raw_response, *timing, user_id, photo_id),
            )
        else:
            conn.execute(
                f"""
                UPDATE extractions
                SET extractor = ?, extracted_at = ?, raw_response = ?, {_EXTRACTION_TIMING_SET}
                WHERE user_id = ? AND photo_id = ?
                """,
                (extractor, extracted_at, raw_response, *timing, user_id, photo_id),
            )
        return

    conn.execute(
        """
        INSERT INTO extractions (
            user_id, photo_id, extractor, extracted_at, raw_response,
            llm_ms, other_ms, model, product_count, extraction_error, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (user_id, photo_id, extractor, extracted_at, raw_response, llm_ms, other_ms, model, len(products), pipeline_status),
    )


def set_extraction_pipeline_status(user_id: str, photo_id: str, status: str) -> None:
    if status not in _PIPELINE_STATUSES:
        raise ValueError(f"Invalid pipeline status: {status}")
    conn = get_conn()
    conn.execute(
        """
        UPDATE extractions
        SET status = ?
        WHERE user_id = ? AND photo_id = ?
        """,
        (status, user_id, photo_id),
    )


def _persist_photo_extraction(
    user_id: str,
    photo_id: str,
    *,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    replace: bool,
    reextracted: bool = False,
    llm_ms: int | None = None,
    other_ms: int | None = None,
    model: str | None = None,
    photo_type: str | None = None,
) -> int:
    now = utc_now()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    if photo_type:
        set_photo_type(conn, user_id, photo_id, photo_type)
    _write_extraction(
        conn,
        user_id=user_id,
        photo_id=photo_id,
        extractor=extractor,
        raw_response=raw_response,
        products=products,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        replace=replace,
        reextracted=reextracted,
    )
    from extract_server.db.sightings import delete_sightings_for_photo, insert_sightings

    if replace:
        delete_sightings_for_photo(conn, user_id, photo_id)
    insert_sightings(conn, user_id=user_id, photo_id=photo_id, products=products, now=now)
    conn.commit()
    return len(products)


def save_photo_extraction(
    user_id: str,
    photo_id: str,
    *,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    llm_ms: int | None = None,
    other_ms: int | None = None,
    model: str | None = None,
    photo_type: str | None = None,
) -> int:
    return _persist_photo_extraction(
        user_id,
        photo_id,
        extractor=extractor,
        raw_response=raw_response,
        products=products,
        replace=False,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        photo_type=photo_type,
    )


def replace_photo_extraction(
    user_id: str,
    photo_id: str,
    *,
    extractor: str,
    raw_response: str | None,
    products: list[dict[str, Any]],
    reextracted: bool = False,
    llm_ms: int | None = None,
    other_ms: int | None = None,
    model: str | None = None,
    photo_type: str | None = None,
) -> int:
    return _persist_photo_extraction(
        user_id,
        photo_id,
        extractor=extractor,
        raw_response=raw_response,
        products=products,
        replace=True,
        reextracted=reextracted,
        llm_ms=llm_ms,
        other_ms=other_ms,
        model=model,
        photo_type=photo_type,
    )


def mark_manually_edited(conn: sqlite3.Connection, user_id: str, photo_id: str) -> None:
    conn.execute(
        """
        UPDATE extractions
        SET manually_edited_at = ?
        WHERE user_id = ? AND photo_id = ?
        """,
        (toronto_now(), user_id, photo_id),
    )


def ensure_manual_extraction(conn: sqlite3.Connection, user_id: str, photo_id: str) -> None:
    exists = conn.execute(
        "SELECT 1 FROM extractions WHERE user_id = ? AND photo_id = ?",
        (user_id, photo_id),
    ).fetchone()
    if exists is None:
        conn.execute(
            """
            INSERT INTO extractions (
                user_id, photo_id, extractor, extracted_at, raw_response
            ) VALUES (?, ?, 'manual', ?, NULL)
            """,
            (user_id, photo_id, toronto_now()),
        )
