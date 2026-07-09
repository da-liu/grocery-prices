from __future__ import annotations

import json
import logging
from typing import Any

from extract_server.db._helpers import utc_now
from extract_server.db.connection import get_conn
from extract_server.db.similarity import (
    load_embeddings_for_user,
    replace_relations,
    upsert_reverse_relation,
)
from extract_server.extraction.embeddings import ensure_embeddings
from extract_server.extraction.matching import MatchSighting, rank_related, sighting_from_row

logger = logging.getLogger(__name__)


def load_match_catalog(user_id: str) -> list[MatchSighting]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, photo_id, product_name, other
        FROM product_sightings
        WHERE user_id = ?
        ORDER BY created_at, id
        """,
        (user_id,),
    ).fetchall()
    catalog: list[MatchSighting] = []
    for row in rows:
        data = dict(row)
        data["other"] = json.loads(data.get("other") or "{}")
        catalog.append(sighting_from_row(data))
    return catalog


def recompute_relations_for_sighting(
    user_id: str,
    sighting_id: str,
    *,
    catalog: list[MatchSighting] | None = None,
    vectors: dict[str, list[float]] | None = None,
    api_key: str | None = None,
) -> list[tuple[str, float]]:
    catalog = catalog or load_match_catalog(user_id)
    source = next((item for item in catalog if item.id == sighting_id), None)
    if source is None:
        return []

    if vectors is None:
        vectors = load_embeddings_for_user(user_id)
        missing = [item for item in catalog if item.id not in vectors]
        if missing:
            vectors.update(ensure_embeddings(user_id, missing, api_key=api_key))

    refs = rank_related(source, catalog, vectors=vectors)
    conn = get_conn()
    now = utc_now()
    conn.execute("BEGIN IMMEDIATE")
    replace_relations(conn, user_id=user_id, source_sighting_id=sighting_id, refs=refs, now=now)
    for related_id, score in refs:
        upsert_reverse_relation(
            conn,
            user_id=user_id,
            source_sighting_id=related_id,
            related_sighting_id=sighting_id,
            score=score,
            now=now,
        )
    conn.commit()
    return refs


def match_sightings(
    user_id: str,
    sighting_ids: list[str],
    *,
    api_key: str | None = None,
) -> None:
    if not sighting_ids:
        return

    catalog = load_match_catalog(user_id)
    catalog_by_id = {item.id: item for item in catalog}
    targets = [catalog_by_id[sid] for sid in sighting_ids if sid in catalog_by_id]
    if not targets:
        return

    vectors = load_embeddings_for_user(user_id)
    vectors.update(ensure_embeddings(user_id, catalog, api_key=api_key))

    touched: set[str] = set(sighting_ids)
    for sighting_id in sighting_ids:
        if sighting_id not in catalog_by_id:
            continue
        refs = recompute_relations_for_sighting(
            user_id,
            sighting_id,
            catalog=catalog,
            vectors=vectors,
            api_key=api_key,
        )
        touched.update(related_id for related_id, _score in refs)

    for sighting_id in touched - set(sighting_ids):
        recompute_relations_for_sighting(
            user_id,
            sighting_id,
            catalog=catalog,
            vectors=vectors,
            api_key=api_key,
        )


def recompute_relations_for_peers(
    user_id: str,
    peer_sighting_ids: list[str],
    *,
    api_key: str | None = None,
) -> None:
    if not peer_sighting_ids:
        return
    catalog = load_match_catalog(user_id)
    catalog_ids = {item.id for item in catalog}
    targets = [sid for sid in peer_sighting_ids if sid in catalog_ids]
    if not targets:
        return
    vectors = load_embeddings_for_user(user_id)
    vectors.update(ensure_embeddings(user_id, catalog, api_key=api_key))
    for sighting_id in targets:
        recompute_relations_for_sighting(
            user_id,
            sighting_id,
            catalog=catalog,
            vectors=vectors,
            api_key=api_key,
        )


def sighting_ids_for_photo(user_id: str, photo_id: str) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id
        FROM product_sightings
        WHERE user_id = ? AND photo_id = ?
        ORDER BY line_index
        """,
        (user_id, photo_id),
    ).fetchall()
    return [row["id"] for row in rows]


def match_photo(user_id: str, photo_id: str, *, api_key: str | None = None) -> None:
    sighting_ids = sighting_ids_for_photo(user_id, photo_id)
    match_sightings(user_id, sighting_ids, api_key=api_key)
