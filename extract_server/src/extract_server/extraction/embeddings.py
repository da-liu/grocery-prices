from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import httpx

from extract_server.db.connection import get_conn
from extract_server.db.similarity import delete_embedding, upsert_embedding
from extract_server.extraction.matching import MatchSighting

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 8
DEFAULT_EMBED_MODEL = "gemini-embedding-001"
DEFAULT_EMBED_DIMENSIONS = 768
DEFAULT_TASK_TYPE = "SEMANTIC_SIMILARITY"


def embed_model() -> str:
    return os.environ.get("GROCERY_EMBED_MODEL", DEFAULT_EMBED_MODEL)


def embed_dimensions() -> int:
    return int(os.environ.get("GROCERY_EMBED_DIMENSIONS", str(DEFAULT_EMBED_DIMENSIONS)))


def embedding_input_text(product_name: str) -> str:
    return product_name


class EmbeddingClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.Client(timeout=60.0)

    def embed_batch(
        self,
        *,
        model: str,
        texts: list[str],
        task_type: str | None = DEFAULT_TASK_TYPE,
        dimensions: int | None = None,
        max_retries: int = 6,
    ) -> list[list[float]]:
        if not texts:
            return []
        dim = dimensions if dimensions is not None else embed_dimensions()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
        requests = []
        for text in texts:
            req: dict[str, Any] = {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": dim,
            }
            if task_type:
                req["taskType"] = task_type
            requests.append(req)

        for attempt in range(max_retries):
            response = self.client.post(url, params={"key": self.api_key}, json={"requests": requests})
            if response.status_code == 200:
                payload = response.json()
                return [item["values"] for item in payload["embeddings"]]
            if response.status_code == 429 and attempt < max_retries - 1:
                wait_s = min(60.0, 5.0 * (2**attempt))
                retry_match = re.search(r"retry in ([0-9.]+)s", response.text, re.IGNORECASE)
                if retry_match:
                    wait_s = max(wait_s, float(retry_match.group(1)) + 1.0)
                logger.warning("embedding_rate_limited wait_s=%.1f", wait_s)
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Embedding API {response.status_code}: {response.text[:500]}")
        raise RuntimeError("Embedding API retries exhausted")


def configured_embedding_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY")


def ensure_embeddings(
    user_id: str,
    sightings: list[MatchSighting],
    *,
    api_key: str | None = None,
) -> dict[str, list[float]]:
    if not sightings:
        return {}

    key = api_key or configured_embedding_api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required for product embeddings")

    conn = get_conn()
    model = embed_model()
    dimensions = embed_dimensions()
    to_embed: list[tuple[str, str]] = []
    vectors: dict[str, list[float]] = {}

    for sighting in sightings:
        input_text = embedding_input_text(sighting.product_name)
        row = conn.execute(
            """
            SELECT input_text, vector
            FROM product_embeddings
            WHERE user_id = ? AND sighting_id = ?
            """,
            (user_id, sighting.id),
        ).fetchone()
        if row is not None and row["input_text"] == input_text:
            blob = row["vector"]
            count = len(blob) // 4
            import struct

            vectors[sighting.id] = list(struct.unpack(f"<{count}f", blob))
            continue
        to_embed.append((sighting.id, input_text))

    if not to_embed:
        return vectors

    client = EmbeddingClient(key)
    conn.execute("BEGIN IMMEDIATE")
    try:
        for start in range(0, len(to_embed), EMBED_BATCH_SIZE):
            batch = to_embed[start : start + EMBED_BATCH_SIZE]
            texts = [text for _, text in batch]
            embedded = client.embed_batch(model=model, texts=texts)
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for (sighting_id, input_text), vector in zip(batch, embedded, strict=True):
                upsert_embedding(
                    conn,
                    user_id=user_id,
                    sighting_id=sighting_id,
                    model=model,
                    dimensions=dimensions,
                    input_text=input_text,
                    vector=vector,
                    now=now,
                )
                vectors[sighting_id] = vector
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return vectors


def invalidate_embedding_if_needed(
    conn,
    user_id: str,
    sighting_id: str,
    *,
    product_name: str,
    barcode: str | None,
) -> bool:
    row = conn.execute(
        """
        SELECT input_text
        FROM product_embeddings
        WHERE user_id = ? AND sighting_id = ?
        """,
        (user_id, sighting_id),
    ).fetchone()
    if row is None:
        return False
    expected = embedding_input_text(product_name)
    if row["input_text"] == expected:
        return False
    delete_embedding(conn, user_id, sighting_id)
    return True
