from __future__ import annotations

import sqlite3
import struct
from typing import Any

from extract_server.db._helpers import utc_now
from extract_server.db.connection import get_conn

def _vector_pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _vector_unpack(blob: bytes) -> list[float]:
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def init_embeddings_table() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS product_embeddings (
            sighting_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            input_text TEXT NOT NULL,
            vector BLOB NOT NULL,
            embedded_at TEXT NOT NULL,
            FOREIGN KEY (sighting_id) REFERENCES product_sightings(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_embeddings_user ON product_embeddings(user_id);
        """
    )


def init_relations_table() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS product_relations (
            user_id TEXT NOT NULL,
            source_sighting_id TEXT NOT NULL,
            related_sighting_id TEXT NOT NULL,
            score REAL NOT NULL,
            rank INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, source_sighting_id, related_sighting_id),
            FOREIGN KEY (source_sighting_id) REFERENCES product_sightings(id) ON DELETE CASCADE,
            FOREIGN KEY (related_sighting_id) REFERENCES product_sightings(id) ON DELETE CASCADE,
            CHECK (source_sighting_id != related_sighting_id)
        );
        CREATE INDEX IF NOT EXISTS idx_relations_source
            ON product_relations(user_id, source_sighting_id, rank);
        """
    )


def get_embedding(user_id: str, sighting_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT sighting_id, user_id, model, dimensions, input_text, vector, embedded_at
        FROM product_embeddings
        WHERE user_id = ? AND sighting_id = ?
        """,
        (user_id, sighting_id),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["vector"] = _vector_unpack(data["vector"])
    return data


def load_embeddings_for_user(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, list[float]]:
    db = conn or get_conn()
    rows = db.execute(
        """
        SELECT sighting_id, vector
        FROM product_embeddings
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()
    return {row["sighting_id"]: _vector_unpack(row["vector"]) for row in rows}


def upsert_embedding(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    sighting_id: str,
    model: str,
    dimensions: int,
    input_text: str,
    vector: list[float],
    now: str | None = None,
) -> None:
    embedded_at = now or utc_now()
    conn.execute(
        """
        INSERT INTO product_embeddings (
            sighting_id, user_id, model, dimensions, input_text, vector, embedded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sighting_id) DO UPDATE SET
            model = excluded.model,
            dimensions = excluded.dimensions,
            input_text = excluded.input_text,
            vector = excluded.vector,
            embedded_at = excluded.embedded_at
        """,
        (
            sighting_id,
            user_id,
            model,
            dimensions,
            input_text,
            _vector_pack(vector),
            embedded_at,
        ),
    )


def delete_embedding(conn: sqlite3.Connection, user_id: str, sighting_id: str) -> None:
    conn.execute(
        "DELETE FROM product_embeddings WHERE user_id = ? AND sighting_id = ?",
        (user_id, sighting_id),
    )


def replace_relations(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    source_sighting_id: str,
    refs: list[tuple[str, float]],
    now: str | None = None,
) -> None:
    timestamp = now or utc_now()
    conn.execute(
        """
        DELETE FROM product_relations
        WHERE user_id = ? AND source_sighting_id = ?
        """,
        (user_id, source_sighting_id),
    )
    for rank, (related_id, score) in enumerate(refs, start=1):
        conn.execute(
            """
            INSERT INTO product_relations (
                user_id, source_sighting_id, related_sighting_id, score, rank,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, source_sighting_id, related_id, score, rank, timestamp, timestamp),
        )


def upsert_reverse_relation(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    source_sighting_id: str,
    related_sighting_id: str,
    score: float,
    now: str | None = None,
) -> None:
    timestamp = now or utc_now()
    existing = conn.execute(
        """
        SELECT rank FROM product_relations
        WHERE user_id = ? AND source_sighting_id = ? AND related_sighting_id = ?
        """,
        (user_id, source_sighting_id, related_sighting_id),
    ).fetchone()
    if existing is not None:
        conn.execute(
            """
            UPDATE product_relations
            SET score = ?, updated_at = ?
            WHERE user_id = ? AND source_sighting_id = ? AND related_sighting_id = ?
            """,
            (score, timestamp, user_id, source_sighting_id, related_sighting_id),
        )
        return

    max_rank_row = conn.execute(
        """
        SELECT COALESCE(MAX(rank), 0) AS max_rank
        FROM product_relations
        WHERE user_id = ? AND source_sighting_id = ?
        """,
        (user_id, source_sighting_id),
    ).fetchone()
    rank = int(max_rank_row["max_rank"]) + 1 if max_rank_row else 1
    conn.execute(
        """
        INSERT INTO product_relations (
            user_id, source_sighting_id, related_sighting_id, score, rank,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, source_sighting_id, related_sighting_id, score, rank, timestamp, timestamp),
    )


def delete_relations_for_sighting(
    conn: sqlite3.Connection,
    user_id: str,
    sighting_id: str,
) -> None:
    conn.execute(
        """
        DELETE FROM product_relations
        WHERE user_id = ?
          AND (source_sighting_id = ? OR related_sighting_id = ?)
        """,
        (user_id, sighting_id, sighting_id),
    )


def load_relations_by_source(
    user_id: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, list[dict[str, Any]]]:
    db = conn or get_conn()
    rows = db.execute(
        """
        SELECT source_sighting_id, related_sighting_id, score, rank
        FROM product_relations
        WHERE user_id = ?
        ORDER BY source_sighting_id, rank
        """,
        (user_id,),
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["source_sighting_id"], []).append(
            {
                "product_id": row["related_sighting_id"],
                "score": row["score"],
            }
        )
    return grouped


def list_peer_sighting_ids(
    conn: sqlite3.Connection,
    user_id: str,
    sighting_id: str,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT peer_id FROM (
            SELECT related_sighting_id AS peer_id
            FROM product_relations
            WHERE user_id = ? AND source_sighting_id = ?
            UNION
            SELECT source_sighting_id AS peer_id
            FROM product_relations
            WHERE user_id = ? AND related_sighting_id = ?
        )
        """,
        (user_id, sighting_id, user_id, sighting_id),
    ).fetchall()
    return [row["peer_id"] for row in rows]
