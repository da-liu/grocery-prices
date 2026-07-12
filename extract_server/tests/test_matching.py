from __future__ import annotations

import math
import uuid

from extract_server.extraction.matching import (
    MatchSighting,
    rescale_cosine,
    score_pair,
    score_pair_detail,
)


def _sighting(
    *,
    name: str,
    barcode: str | None = None,
    category: str = "pantry",
    brand: str | None = None,
    photo_id: str = "p1",
    sid: str | None = None,
) -> MatchSighting:
    return MatchSighting(
        id=sid or uuid.uuid4().hex,
        photo_id=photo_id,
        product_name=name,
        category=category,
        brand=brand,
        barcode=barcode,
    )


def test_barcode_match_ignores_name_mismatch():
    a = _sighting(name="Lay's Classic Chips", barcode="123", category="snacks", brand="Lay's")
    b = _sighting(name="Dawn Dish Soap", barcode="123", category="cleaning", photo_id="p2")
    assert score_pair(a, b) == 1.0
    detail = score_pair_detail(a, b)
    assert detail.path == "barcode"
    assert detail.final_score == 1.0


def test_barcode_match_when_names_agree():
    a = _sighting(name="Organic Milk 2L", barcode="999", category="dairy")
    b = _sighting(name="Organic Milk 2L", barcode="999", category="dairy", photo_id="p2")
    assert score_pair(a, b) == 1.0


def test_exact_name_matches_despite_barcode_conflict():
    a = _sighting(name="Colgate Total", barcode="111", category="personal care")
    b = _sighting(name="Colgate Total", barcode="222", category="personal care", photo_id="p2")
    assert score_pair(a, b) == 1.0
    assert score_pair_detail(a, b).path == "exact_name"


def test_exact_name_matches_generic_name():
    a = _sighting(name="Thyme", category="produce")
    b = _sighting(name="Thyme", category="produce", photo_id="p2")
    assert score_pair(a, b) == 1.0


def test_exact_name_generic_allowed_with_brand_and_category():
    a = _sighting(name="Milk", category="dairy", brand="Beatrice")
    b = _sighting(name="Milk", category="dairy", brand="Beatrice", photo_id="p2")
    assert score_pair(a, b) == 1.0


def test_exact_name_matches_despite_category_mismatch():
    a = _sighting(name="Colgate Total", category="personal care")
    b = _sighting(name="Colgate Total", category="pantry", photo_id="p2")
    assert score_pair(a, b) == 1.0


def test_rescale_cosine_floor_maps_band_to_unit_interval():
    assert rescale_cosine(0.70, floor=0.70) == 0.0
    assert rescale_cosine(0.69, floor=0.70) == 0.0
    assert rescale_cosine(1.0, floor=0.70) == 1.0
    assert abs(rescale_cosine(0.85, floor=0.70) - 0.5) < 1e-9
    assert abs(rescale_cosine(0.755, floor=0.70) - (0.755 - 0.70) / 0.30) < 1e-9


def test_composite_uses_embedding_and_token_jaccard():
    a = _sighting(name="Spring Home Glutinous Rice Ball Sesame", category="frozen")
    b = _sighting(name="Spring Home Glutinous Rice Ball Peanut", category="frozen", photo_id="p2")
    vector = [1.0, 0.0, 0.0]
    score = score_pair(a, b, vector_a=vector, vector_b=vector)
    assert score > 0.5
    detail = score_pair_detail(a, b, vector_a=vector, vector_b=vector)
    assert detail.path == "composite"
    assert detail.embedding_cosine == 1.0
    assert detail.embedding_score == 1.0
    assert detail.cosine_floor == 0.70
    assert abs(detail.final_score - (0.75 * detail.embedding_score + 0.25 * detail.token_jaccard)) < 1e-9
    assert "cos - 0.7" in (detail.formula or "")


def test_composite_low_cosine_near_floor_scores_near_token_only():
    a = _sighting(name="Tabasco Pepper Sauce", category="pantry")
    b = _sighting(name="Previously Frozen Tuna Steaks", category="seafood", photo_id="p2")
    # Cosine ≈ 0.70 → emb ≈ 0 after floor remap
    vector_a = [1.0, 0.0]
    vector_b = [0.70, math.sqrt(1.0 - 0.70**2)]
    detail = score_pair_detail(a, b, vector_a=vector_a, vector_b=vector_b)
    assert detail.path == "composite"
    assert abs(detail.embedding_cosine - 0.70) < 1e-6
    assert detail.embedding_score == 0.0
    assert detail.final_score == 0.25 * detail.token_jaccard
    assert detail.token_jaccard == 0.0
    assert detail.final_score == 0.0


def test_custom_weights_change_composite():
    a = _sighting(name="Alpha Beta Gamma Unique", category="pantry")
    b = _sighting(name="Alpha Beta Delta Other", category="pantry", photo_id="p2")
    # High embedding similarity, lower token overlap
    vector_a = [1.0, 0.0, 0.0]
    vector_b = [0.95, 0.3122, 0.0]
    production = score_pair_detail(a, b, vector_a=vector_a, vector_b=vector_b)
    tok_heavy = score_pair_detail(
        a, b, vector_a=vector_a, vector_b=vector_b, emb_weight=0.1, tok_weight=0.9
    )
    assert production.path == "composite"
    assert tok_heavy.path == "composite"
    assert production.embedding_score != production.token_jaccard
    assert abs(tok_heavy.final_score - production.final_score) > 1e-6
    assert abs(
        tok_heavy.final_score - (0.1 * tok_heavy.embedding_score + 0.9 * tok_heavy.token_jaccard)
    ) < 1e-9


def test_match_photo_links_barcode_duplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("extract_server.extraction.paths.DATA_DIR", tmp_path / "data")

    from extract_server.db import init_db, register_user, save_photo
    from extract_server.db._ids import blob_key
    from extract_server.db.extractions import save_photo_extraction
    from extract_server.db.connection import get_conn
    from extract_server.db.similarity import load_relations_by_source
    from extract_server.extraction.match_catalog import match_sightings

    init_db()
    user = register_user("match-user", "password12345")

    def fake_embed(user_id, sightings, api_key=None):
        return {item.id: [1.0, 0.0, 0.0] for item in sightings}

    monkeypatch.setattr("extract_server.extraction.match_catalog.ensure_embeddings", fake_embed)

    conn = get_conn()
    for index, photo_id in enumerate(("IMG_A", "IMG_B"), start=1):
        save_photo(
            user.id,
            photo_id=photo_id,
            blob_key=blob_key(user.id, "2026_07_08", photo_id, ".jpg"),
            content_hash=f"hash-{index}",
            gps_latitude=None,
            gps_longitude=None,
            captured_at=None,
            store_location_id=None,
        )
        save_photo_extraction(
            user.id,
            photo_id,
            extractor="test",
            raw_response=None,
            products=[
                {
                    "product_name": "Synear Rice Ball",
                    "price": 3.99,
                    "category": "frozen",
                    "other": {"barcode": "555"},
                }
            ],
        )

    rows = conn.execute(
        "SELECT id, photo_id FROM product_sightings WHERE user_id = ? ORDER BY photo_id",
        (user.id,),
    ).fetchall()
    assert len(rows) == 2
    match_sightings(user.id, [row["id"] for row in rows])

    relations = load_relations_by_source(user.id)
    assert len(relations) == 2
    ids = {row["id"] for row in rows}
    for row in rows:
        related = relations[row["id"]]
        assert len(related) == 1
        assert related[0]["product_id"] in ids - {row["id"]}
        assert related[0]["score"] == 1.0
