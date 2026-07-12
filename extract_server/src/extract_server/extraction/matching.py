from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Literal

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

PRODUCTION_EMB_WEIGHT = 0.75
PRODUCTION_TOK_WEIGHT = 0.25
# Grocery name embeddings cluster tightly (~0.70–1.0). Stretch that band to [0, 1]
# before applying emb_weight so unrelated pairs no longer dominate the composite.
DEFAULT_EMBED_COSINE_FLOOR = 0.70

MatchPath = Literal["barcode", "exact_name", "composite"]


def match_top_n() -> int:
    return int(os.environ.get("GROCERY_MATCH_TOP_N", "5"))


def match_min_score() -> float:
    return float(os.environ.get("GROCERY_MATCH_MIN_SCORE", "0.5"))


def embed_cosine_floor() -> float:
    return float(os.environ.get("GROCERY_EMBED_COSINE_FLOOR", str(DEFAULT_EMBED_COSINE_FLOOR)))


@dataclass(frozen=True)
class MatchSighting:
    id: str
    photo_id: str
    product_name: str
    category: str = ""
    brand: str | None = None
    barcode: str | None = None


@dataclass(frozen=True)
class MatchScoreDetail:
    final_score: float
    path: MatchPath
    embedding_cosine: float | None
    embedding_score: float
    cosine_floor: float
    token_jaccard: float
    emb_weight: float
    tok_weight: float
    normalized_source: str
    normalized_target: str
    formula: str | None


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


def rescale_cosine(cosine: float, *, floor: float | None = None) -> float:
    """Map cosine from [floor, 1] onto [0, 1], clamped."""
    c_min = embed_cosine_floor() if floor is None else floor
    if c_min >= 1.0:
        return 1.0 if cosine >= 1.0 else 0.0
    t = (cosine - c_min) / (1.0 - c_min)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t


def embedding_score(
    vector_a: list[float] | None,
    vector_b: list[float] | None,
    *,
    floor: float | None = None,
) -> float:
    if vector_a is None or vector_b is None:
        return 0.0
    return rescale_cosine(cosine_similarity(vector_a, vector_b), floor=floor)


def _composite_formula(emb_weight: float, tok_weight: float, cosine_floor: float) -> str:
    return (
        f"{emb_weight} * emb + {tok_weight} * tok "
        f"(emb = clamp((cos - {cosine_floor}) / (1 - {cosine_floor}), 0, 1))"
    )


def score_pair_detail(
    a: MatchSighting,
    b: MatchSighting,
    *,
    vector_a: list[float] | None = None,
    vector_b: list[float] | None = None,
    emb_weight: float = PRODUCTION_EMB_WEIGHT,
    tok_weight: float = PRODUCTION_TOK_WEIGHT,
    cosine_floor: float | None = None,
) -> MatchScoreDetail:
    norm_a = normalize_name(a.product_name)
    norm_b = normalize_name(b.product_name)
    floor = embed_cosine_floor() if cosine_floor is None else cosine_floor
    raw_cosine = (
        cosine_similarity(vector_a, vector_b)
        if vector_a is not None and vector_b is not None
        else None
    )
    emb = (
        rescale_cosine(raw_cosine, floor=floor)
        if raw_cosine is not None
        else 0.0
    )
    tok = token_jaccard(a.product_name, b.product_name, ignore_generic=True)

    if a.barcode and b.barcode and a.barcode == b.barcode:
        return MatchScoreDetail(
            final_score=1.0,
            path="barcode",
            embedding_cosine=raw_cosine,
            embedding_score=emb,
            cosine_floor=floor,
            token_jaccard=tok,
            emb_weight=emb_weight,
            tok_weight=tok_weight,
            normalized_source=norm_a,
            normalized_target=norm_b,
            formula=None,
        )

    if norm_a == norm_b:
        return MatchScoreDetail(
            final_score=1.0,
            path="exact_name",
            embedding_cosine=raw_cosine,
            embedding_score=emb,
            cosine_floor=floor,
            token_jaccard=tok,
            emb_weight=emb_weight,
            tok_weight=tok_weight,
            normalized_source=norm_a,
            normalized_target=norm_b,
            formula=None,
        )

    final = emb_weight * emb + tok_weight * tok
    return MatchScoreDetail(
        final_score=final,
        path="composite",
        embedding_cosine=raw_cosine,
        embedding_score=emb,
        cosine_floor=floor,
        token_jaccard=tok,
        emb_weight=emb_weight,
        tok_weight=tok_weight,
        normalized_source=norm_a,
        normalized_target=norm_b,
        formula=_composite_formula(emb_weight, tok_weight, floor),
    )


def score_pair(
    a: MatchSighting,
    b: MatchSighting,
    *,
    vector_a: list[float] | None = None,
    vector_b: list[float] | None = None,
) -> float:
    return score_pair_detail(a, b, vector_a=vector_a, vector_b=vector_b).final_score


def rank_related(
    source: MatchSighting,
    catalog: list[MatchSighting],
    *,
    vectors: dict[str, list[float]],
    top_n: int | None = None,
    min_score: float | None = None,
    emb_weight: float = PRODUCTION_EMB_WEIGHT,
    tok_weight: float = PRODUCTION_TOK_WEIGHT,
    exclude_same_photo: bool = False,
) -> list[tuple[str, float]]:
    details = rank_related_detail(
        source,
        catalog,
        vectors=vectors,
        top_n=top_n,
        min_score=min_score,
        emb_weight=emb_weight,
        tok_weight=tok_weight,
        exclude_same_photo=exclude_same_photo,
    )
    return [(item_id, detail.final_score) for item_id, detail in details]


def rank_related_detail(
    source: MatchSighting,
    catalog: list[MatchSighting],
    *,
    vectors: dict[str, list[float]],
    top_n: int | None = None,
    min_score: float | None = None,
    emb_weight: float = PRODUCTION_EMB_WEIGHT,
    tok_weight: float = PRODUCTION_TOK_WEIGHT,
    exclude_same_photo: bool = False,
) -> list[tuple[str, MatchScoreDetail]]:
    limit = top_n if top_n is not None else match_top_n()
    threshold = min_score if min_score is not None else match_min_score()
    scored: list[tuple[str, MatchScoreDetail]] = []
    source_vector = vectors.get(source.id)

    for candidate in catalog:
        if candidate.id == source.id:
            continue
        if exclude_same_photo and candidate.photo_id == source.photo_id:
            continue
        detail = score_pair_detail(
            source,
            candidate,
            vector_a=source_vector,
            vector_b=vectors.get(candidate.id),
            emb_weight=emb_weight,
            tok_weight=tok_weight,
        )
        if detail.final_score >= threshold:
            scored.append((candidate.id, detail))

    scored.sort(key=lambda item: (-item[1].final_score, item[0]))
    return scored[:limit]


def sighting_from_row(row: dict[str, Any]) -> MatchSighting:
    other = row.get("other") or {}
    if isinstance(other, str):
        other = json.loads(other or "{}")
    return MatchSighting(
        id=row["id"],
        photo_id=row["photo_id"],
        product_name=row["product_name"],
        category=str(other.get("category") or row.get("category") or ""),
        brand=other.get("brand") if isinstance(other.get("brand"), str) else None,
        barcode=other.get("barcode") if isinstance(other.get("barcode"), str) else None,
    )
