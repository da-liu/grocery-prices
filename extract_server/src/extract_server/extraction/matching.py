from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

from extract_server.extraction.scoring import normalize_name

STOP_TOKENS = frozenset({
    "with", "and", "the", "a", "an", "of", "for", "in", "on", "w", "ea", "pkg", "pack",
    "value", "fresh", "food", "foods", "mart", "label", "superior", "bridge",
})

GENERIC_PRODUCT_TOKENS = frozenset({
    "rice", "ball", "balls", "pork", "soy", "sauce", "milk", "egg", "eggs", "tofu",
    "chips", "tomato", "tomatoes", "pasta", "frozen", "fresh", "boneless", "whole",
    "thyme", "herb", "herbs", "spice", "spices",
})


def match_top_n() -> int:
    return int(os.environ.get("GROCERY_MATCH_TOP_N", "5"))


def match_min_score() -> float:
    return float(os.environ.get("GROCERY_MATCH_MIN_SCORE", "0.65"))


@dataclass(frozen=True)
class MatchSighting:
    id: str
    photo_id: str
    product_name: str
    category: str = ""
    brand: str | None = None
    barcode: str | None = None


def tokenize(name: str) -> list[str]:
    return [t for t in normalize_name(name).split() if t and t not in STOP_TOKENS]


def token_jaccard(a: str, b: str, *, ignore_generic: bool = False) -> float:
    ta = {t for t in tokenize(a) if not (ignore_generic and t in GENERIC_PRODUCT_TOKENS)}
    tb = {t for t in tokenize(b) if not (ignore_generic and t in GENERIC_PRODUCT_TOKENS)}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_score(vector_a: list[float] | None, vector_b: list[float] | None) -> float:
    if vector_a is None or vector_b is None:
        return 0.0
    return (cosine_similarity(vector_a, vector_b) + 1.0) / 2.0


def score_pair(
    a: MatchSighting,
    b: MatchSighting,
    *,
    vector_a: list[float] | None = None,
    vector_b: list[float] | None = None,
) -> float:
    if a.barcode and b.barcode and a.barcode == b.barcode:
        return 1.0

    if normalize_name(a.product_name) == normalize_name(b.product_name):
        return 1.0

    emb = embedding_score(vector_a, vector_b)
    tok = token_jaccard(a.product_name, b.product_name, ignore_generic=True)
    return 0.75 * emb + 0.25 * tok


def rank_related(
    source: MatchSighting,
    catalog: list[MatchSighting],
    *,
    vectors: dict[str, list[float]],
    top_n: int | None = None,
    min_score: float | None = None,
) -> list[tuple[str, float]]:
    limit = top_n if top_n is not None else match_top_n()
    threshold = min_score if min_score is not None else match_min_score()
    scored: list[tuple[str, float]] = []
    source_vector = vectors.get(source.id)

    for candidate in catalog:
        if candidate.id == source.id:
            continue
        if candidate.photo_id == source.photo_id:
            continue
        score = score_pair(
            source,
            candidate,
            vector_a=source_vector,
            vector_b=vectors.get(candidate.id),
        )
        if score >= threshold:
            scored.append((candidate.id, score))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:limit]


def sighting_from_row(row: dict[str, Any]) -> MatchSighting:
    other = row.get("other") or {}
    if isinstance(other, str):
        import json

        other = json.loads(other or "{}")
    return MatchSighting(
        id=row["id"],
        photo_id=row["photo_id"],
        product_name=row["product_name"],
        category=str(other.get("category") or row.get("category") or ""),
        brand=other.get("brand") if isinstance(other.get("brand"), str) else None,
        barcode=other.get("barcode") if isinstance(other.get("barcode"), str) else None,
    )
