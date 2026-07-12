#!/usr/bin/env python3
"""Clear product_relations and recompute ranking for all (or one user's) sightings.

Uses current production matching settings:
  - emb = clamp((cos - floor) / (1 - floor), 0, 1)
  - final = 0.75 * emb + 0.25 * tok
  - exclude_same_photo = False
  - min_score / top_n from env (defaults 0.5 / 5)

Embeddings are reused when present; missing ones are generated via Gemini.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from extract_server.db import close_all_connections, init_db  # noqa: E402
from extract_server.db.connection import get_conn  # noqa: E402
from extract_server.db.similarity import load_embeddings_for_user  # noqa: E402
from extract_server.extraction.embeddings import (  # noqa: E402
    configured_embedding_api_key,
    ensure_embeddings,
)
from extract_server.extraction.match_catalog import (  # noqa: E402
    load_match_catalog,
    recompute_relations_for_sighting,
)
from extract_server.extraction.matching import (  # noqa: E402
    DEFAULT_EMBED_COSINE_FLOOR,
    PRODUCTION_EMB_WEIGHT,
    PRODUCTION_TOK_WEIGHT,
    embed_cosine_floor,
    match_min_score,
    match_top_n,
)


def _list_user_ids(user_id: str | None) -> list[str]:
    conn = get_conn()
    if user_id:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise SystemExit(f"User not found: {user_id}")
        return [user_id]
    rows = conn.execute(
        """
        SELECT DISTINCT user_id
        FROM product_sightings
        ORDER BY user_id
        """
    ).fetchall()
    return [row["user_id"] for row in rows]


def _clear_relations(user_id: str | None) -> int:
    conn = get_conn()
    if user_id:
        cur = conn.execute(
            "DELETE FROM product_relations WHERE user_id = ?",
            (user_id,),
        )
    else:
        cur = conn.execute("DELETE FROM product_relations")
    conn.commit()
    return int(cur.rowcount)


def _relation_count(user_id: str | None = None) -> int:
    conn = get_conn()
    if user_id:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM product_relations WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS c FROM product_relations").fetchone()
    return int(row["c"])


def rematch_user(user_id: str, *, api_key: str | None) -> dict[str, int]:
    catalog = load_match_catalog(user_id)
    if not catalog:
        return {"sightings": 0, "with_relations": 0, "relation_edges": 0}

    vectors = load_embeddings_for_user(user_id)
    missing = [item for item in catalog if item.id not in vectors]
    if missing:
        print(f"  embedding {len(missing)} missing of {len(catalog)}…")
        vectors.update(ensure_embeddings(user_id, catalog, api_key=api_key))

    with_relations = 0
    edge_count = 0
    total = len(catalog)
    t0 = time.perf_counter()
    for index, sighting in enumerate(catalog, start=1):
        refs = recompute_relations_for_sighting(
            user_id,
            sighting.id,
            catalog=catalog,
            vectors=vectors,
            api_key=api_key,
        )
        if refs:
            with_relations += 1
            edge_count += len(refs)
        if index == total or index % 25 == 0:
            elapsed = time.perf_counter() - t0
            print(
                f"  ranked {index}/{total}  "
                f"sources_with_hits={with_relations}  edges={edge_count}  "
                f"({elapsed:.1f}s)"
            )

    return {
        "sightings": total,
        "with_relations": with_relations,
        "relation_edges": edge_count,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id",
        default=None,
        help="Only rematch this user (default: all users with sightings)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts and settings; do not delete or write relations",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    init_db()

    api_key = configured_embedding_api_key()
    user_ids = _list_user_ids(args.user_id)

    print("settings")
    print(f"  emb_weight={PRODUCTION_EMB_WEIGHT}  tok_weight={PRODUCTION_TOK_WEIGHT}")
    print(f"  cosine_floor={embed_cosine_floor()} (default {DEFAULT_EMBED_COSINE_FLOOR})")
    print(f"  min_score={match_min_score()}  top_n={match_top_n()}")
    print(f"  exclude_same_photo=False (production default)")
    print(f"  users={len(user_ids)}  dry_run={args.dry_run}")
    print(f"  relations_before={_relation_count(args.user_id)}")

    if args.dry_run:
        for user_id in user_ids:
            catalog = load_match_catalog(user_id)
            vectors = load_embeddings_for_user(user_id)
            print(
                f"  user {user_id}: sightings={len(catalog)} "
                f"embeddings={len(vectors)}"
            )
        return 0

    if not api_key:
        # Still ok if every sighting already has an embedding.
        print("warning: GEMINI_API_KEY unset; missing embeddings will fail")

    deleted = _clear_relations(args.user_id)
    print(f"cleared {deleted} old relation rows")

    totals = {"sightings": 0, "with_relations": 0, "relation_edges": 0}
    for user_id in user_ids:
        print(f"user {user_id}")
        stats = rematch_user(user_id, api_key=api_key)
        for key, value in stats.items():
            totals[key] += value
        print(
            f"  done sightings={stats['sightings']} "
            f"with_relations={stats['with_relations']} "
            f"edges={stats['relation_edges']}"
        )

    print("summary")
    print(f"  sightings={totals['sightings']}")
    print(f"  sources_with_relations={totals['with_relations']}")
    print(f"  relation_edges={totals['relation_edges']}")
    print(f"  relations_after={_relation_count(args.user_id)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        close_all_connections()
