from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MatchWeightsBody(BaseModel):
    emb_weight: float = Field(default=0.75, ge=0.0, le=1.0)
    tok_weight: float = Field(default=0.25, ge=0.0, le=1.0)


class MatchExplainBody(MatchWeightsBody):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)


class MatchRankBody(MatchWeightsBody):
    source_id: str = Field(min_length=1)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)
    top_n: int | None = Field(default=None, ge=1, le=500)
    exclude_same_photo: bool = False


class MatchRematchBody(BaseModel):
    sighting_ids: list[str] | None = Field(default=None, max_length=500)
    photo_id: str | None = None

    @model_validator(mode="after")
    def require_target(self) -> MatchRematchBody:
        has_ids = bool(self.sighting_ids)
        has_photo = bool(self.photo_id)
        if not has_ids and not has_photo:
            raise ValueError("Provide sighting_ids and/or photo_id")
        return self


class MatchScoreDetailOut(BaseModel):
    final_score: float
    path: Literal["barcode", "exact_name", "composite"]
    embedding_cosine: float | None
    embedding_score: float
    cosine_floor: float
    token_jaccard: float
    emb_weight: float
    tok_weight: float
    normalized_source: str
    normalized_target: str
    formula: str | None


class MatchExplainResponse(BaseModel):
    source_id: str
    target_id: str
    source_name: str
    target_name: str
    source_photo_id: str
    target_photo_id: str
    detail: MatchScoreDetailOut


class MatchRankCandidateOut(BaseModel):
    product_id: str
    product_name: str
    photo_id: str
    barcode: str | None
    detail: MatchScoreDetailOut


class MatchRankResponse(BaseModel):
    source_id: str
    source_name: str
    source_photo_id: str
    emb_weight: float
    tok_weight: float
    min_score: float
    top_n: int
    exclude_same_photo: bool
    matches: list[MatchRankCandidateOut]


class RelatedRefOut(BaseModel):
    product_id: str
    score: float


class MatchRematchSourceOut(BaseModel):
    sighting_id: str
    related_products: list[RelatedRefOut]


class MatchRematchResponse(BaseModel):
    rematched: list[MatchRematchSourceOut]
