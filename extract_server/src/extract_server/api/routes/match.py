from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from extract_server.api.dependencies import AuthUser, require_user
from extract_server.db.similarity import load_embeddings_for_user, load_relations_by_source
from extract_server.extraction.embeddings import ensure_embeddings
from extract_server.extraction.match_catalog import (
    load_match_catalog,
    match_photo,
    match_sightings,
    sighting_ids_for_photo,
)
from extract_server.extraction.matching import (
    MatchScoreDetail,
    match_min_score,
    match_top_n,
    rank_related_detail,
    score_pair_detail,
)
from extract_server.schemas.match import (
    MatchExplainBody,
    MatchExplainResponse,
    MatchRankBody,
    MatchRankCandidateOut,
    MatchRankResponse,
    MatchRematchBody,
    MatchRematchResponse,
    MatchRematchSourceOut,
    MatchScoreDetailOut,
    RelatedRefOut,
)

router = APIRouter(prefix="/api/match", tags=["match"])


def _detail_out(detail: MatchScoreDetail) -> MatchScoreDetailOut:
    return MatchScoreDetailOut(
        final_score=detail.final_score,
        path=detail.path,
        embedding_cosine=detail.embedding_cosine,
        embedding_score=detail.embedding_score,
        cosine_floor=detail.cosine_floor,
        token_jaccard=detail.token_jaccard,
        emb_weight=detail.emb_weight,
        tok_weight=detail.tok_weight,
        normalized_source=detail.normalized_source,
        normalized_target=detail.normalized_target,
        formula=detail.formula,
    )


def _load_catalog_and_vectors(user_id: str):
    catalog = load_match_catalog(user_id)
    vectors = load_embeddings_for_user(user_id)
    if catalog:
        vectors.update(ensure_embeddings(user_id, catalog))
    return catalog, vectors


@router.post("/explain", response_model=MatchExplainResponse)
def explain_match(
    body: MatchExplainBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> MatchExplainResponse:
    catalog, vectors = _load_catalog_and_vectors(user.id)
    by_id = {item.id: item for item in catalog}
    source = by_id.get(body.source_id)
    target = by_id.get(body.target_id)
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="Product not found")

    detail = score_pair_detail(
        source,
        target,
        vector_a=vectors.get(source.id),
        vector_b=vectors.get(target.id),
        emb_weight=body.emb_weight,
        tok_weight=body.tok_weight,
    )
    return MatchExplainResponse(
        source_id=source.id,
        target_id=target.id,
        source_name=source.product_name,
        target_name=target.product_name,
        source_photo_id=source.photo_id,
        target_photo_id=target.photo_id,
        detail=_detail_out(detail),
    )


@router.post("/rank", response_model=MatchRankResponse)
def rank_matches(
    body: MatchRankBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> MatchRankResponse:
    catalog, vectors = _load_catalog_and_vectors(user.id)
    by_id = {item.id: item for item in catalog}
    source = by_id.get(body.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Product not found")

    threshold = body.min_score if body.min_score is not None else match_min_score()
    limit = body.top_n if body.top_n is not None else match_top_n()
    ranked = rank_related_detail(
        source,
        catalog,
        vectors=vectors,
        top_n=limit,
        min_score=threshold,
        emb_weight=body.emb_weight,
        tok_weight=body.tok_weight,
        exclude_same_photo=body.exclude_same_photo,
    )

    matches: list[MatchRankCandidateOut] = []
    for product_id, detail in ranked:
        candidate = by_id[product_id]
        matches.append(
            MatchRankCandidateOut(
                product_id=candidate.id,
                product_name=candidate.product_name,
                photo_id=candidate.photo_id,
                barcode=candidate.barcode,
                detail=_detail_out(detail),
            )
        )

    return MatchRankResponse(
        source_id=source.id,
        source_name=source.product_name,
        source_photo_id=source.photo_id,
        emb_weight=body.emb_weight,
        tok_weight=body.tok_weight,
        min_score=threshold,
        top_n=limit,
        exclude_same_photo=body.exclude_same_photo,
        matches=matches,
    )


@router.post("/rematch", response_model=MatchRematchResponse)
def rematch_products(
    body: MatchRematchBody,
    user: Annotated[AuthUser, Depends(require_user)],
) -> MatchRematchResponse:
    target_ids: list[str] = list(body.sighting_ids or [])
    if body.photo_id:
        target_ids.extend(sighting_ids_for_photo(user.id, body.photo_id))

    # Preserve order, drop duplicates
    seen: set[str] = set()
    unique_ids: list[str] = []
    for sid in target_ids:
        if sid in seen:
            continue
        seen.add(sid)
        unique_ids.append(sid)

    if not unique_ids:
        raise HTTPException(status_code=404, detail="No products to rematch")

    catalog_ids = {item.id for item in load_match_catalog(user.id)}
    missing = [sid for sid in unique_ids if sid not in catalog_ids]
    if missing and body.photo_id and not body.sighting_ids:
        raise HTTPException(status_code=404, detail="Photo has no products")
    if missing:
        raise HTTPException(status_code=404, detail="Product not found")

    if body.photo_id and not body.sighting_ids:
        match_photo(user.id, body.photo_id)
    else:
        match_sightings(user.id, unique_ids)

    relations = load_relations_by_source(user.id)
    rematched = [
        MatchRematchSourceOut(
            sighting_id=sid,
            related_products=[
                RelatedRefOut(product_id=ref["product_id"], score=ref["score"])
                for ref in relations.get(sid, [])
            ],
        )
        for sid in unique_ids
    ]
    return MatchRematchResponse(rematched=rematched)
