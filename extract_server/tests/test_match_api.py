from __future__ import annotations

import uuid

import pytest


def _register(client, username: str | None = None):
    name = username or f"matchlab_{uuid.uuid4().hex[:8]}"
    res = client.post(
        "/api/auth/register",
        json={"username": name, "password": "password12345"},
    )
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _seed_pair(monkeypatch, names_and_barcodes, vectors=None):
    from extract_server.db import init_db, register_user, save_photo
    from extract_server.db._ids import blob_key
    from extract_server.db.connection import get_conn
    from extract_server.db.extractions import save_photo_extraction

    init_db()
    user = register_user(f"seed_{uuid.uuid4().hex[:8]}", "password12345")

    def fake_embed(user_id, sightings, api_key=None):
        out = {}
        for item in sightings:
            if vectors and item.id in vectors:
                out[item.id] = vectors[item.id]
            else:
                out[item.id] = [1.0, 0.0, 0.0]
        return out

    monkeypatch.setattr("extract_server.extraction.match_catalog.ensure_embeddings", fake_embed)
    monkeypatch.setattr("extract_server.api.routes.match.ensure_embeddings", fake_embed)

    conn = get_conn()
    sighting_ids: list[str] = []
    for index, (name, barcode) in enumerate(names_and_barcodes, start=1):
        photo_id = f"IMG_{index}"
        save_photo(
            user.id,
            photo_id=photo_id,
            blob_key=blob_key(user.id, "2026_07_08", photo_id, ".jpg"),
            content_hash=f"hash-{index}-{uuid.uuid4().hex[:6]}",
            gps_latitude=None,
            gps_longitude=None,
            captured_at=None,
            store_location_id=None,
        )
        other = {"barcode": barcode} if barcode else {}
        save_photo_extraction(
            user.id,
            photo_id,
            extractor="test",
            raw_response=None,
            products=[
                {
                    "product_name": name,
                    "price": 1.0 + index,
                    "category": "pantry",
                    "other": other,
                }
            ],
        )

    rows = conn.execute(
        "SELECT id, product_name, photo_id FROM product_sightings WHERE user_id = ? ORDER BY photo_id",
        (user.id,),
    ).fetchall()
    sighting_ids = [row["id"] for row in rows]
    return user, rows, sighting_ids


@pytest.fixture
def auth_headers(client):
    token = _register(client)
    return {"Authorization": f"Bearer {token}"}


def test_explain_barcode_path(client, monkeypatch):
    user, rows, ids = _seed_pair(
        monkeypatch,
        [("Lay's Chips", "123"), ("Dawn Soap", "123")],
    )
    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": "password12345"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    res = client.post(
        "/api/match/explain",
        headers=headers,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["detail"]["path"] == "barcode"
    assert body["detail"]["final_score"] == 1.0


def test_explain_exact_name_path(client, monkeypatch):
    user, rows, ids = _seed_pair(
        monkeypatch,
        [("Colgate Total", "111"), ("Colgate Total", "222")],
    )
    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": "password12345"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    res = client.post(
        "/api/match/explain",
        headers=headers,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    assert res.status_code == 200
    assert res.json()["detail"]["path"] == "exact_name"


def test_explain_composite_and_custom_weights(client, monkeypatch):
    user, rows, ids = _seed_pair(
        monkeypatch,
        [("Alpha Beta Gamma", None), ("Alpha Beta Delta", None)],
    )
    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": "password12345"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    from extract_server.db.connection import get_conn
    from extract_server.db.similarity import upsert_embedding
    from extract_server.extraction.embeddings import embedding_input_text

    conn = get_conn()
    upsert_embedding(
        conn,
        user_id=user.id,
        sighting_id=ids[0],
        model="test",
        dimensions=3,
        input_text=embedding_input_text(rows[0]["product_name"]),
        vector=[1.0, 0.0, 0.0],
    )
    upsert_embedding(
        conn,
        user_id=user.id,
        sighting_id=ids[1],
        model="test",
        dimensions=3,
        input_text=embedding_input_text(rows[1]["product_name"]),
        vector=[0.0, 1.0, 0.0],
    )
    conn.commit()

    production = client.post(
        "/api/match/explain",
        headers=headers,
        json={"source_id": ids[0], "target_id": ids[1]},
    )
    assert production.status_code == 200
    prod_detail = production.json()["detail"]
    assert prod_detail["path"] == "composite"

    custom = client.post(
        "/api/match/explain",
        headers=headers,
        json={
            "source_id": ids[0],
            "target_id": ids[1],
            "emb_weight": 0.1,
            "tok_weight": 0.9,
        },
    )
    assert custom.status_code == 200
    custom_detail = custom.json()["detail"]
    assert custom_detail["path"] == "composite"
    assert custom_detail["final_score"] != prod_detail["final_score"]
    assert abs(
        custom_detail["final_score"]
        - (0.1 * custom_detail["embedding_score"] + 0.9 * custom_detail["token_jaccard"])
    ) < 1e-6


def test_explain_unknown_product_404(client, auth_headers):
    res = client.post(
        "/api/match/explain",
        headers=auth_headers,
        json={"source_id": "missing", "target_id": "also-missing"},
    )
    assert res.status_code == 404


def test_rank_preview(client, monkeypatch):
    user, rows, ids = _seed_pair(
        monkeypatch,
        [("Synear Rice Ball", "555"), ("Synear Rice Ball", "555"), ("Unrelated Item", None)],
    )
    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": "password12345"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    res = client.post(
        "/api/match/rank",
        headers=headers,
        json={"source_id": ids[0], "min_score": 0.5, "top_n": 10},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    match_ids = {m["product_id"] for m in body["matches"]}
    assert ids[1] in match_ids
    assert ids[0] not in match_ids


def test_rematch_persists_relations(client, monkeypatch):
    user, rows, ids = _seed_pair(
        monkeypatch,
        [("Synear Rice Ball", "555"), ("Synear Rice Ball", "555")],
    )
    login = client.post(
        "/api/auth/login",
        json={"username": user.username, "password": "password12345"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    res = client.post(
        "/api/match/rematch",
        headers=headers,
        json={"sighting_ids": [ids[0]]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["rematched"]) == 1
    related = body["rematched"][0]["related_products"]
    assert len(related) == 1
    assert related[0]["product_id"] == ids[1]
    assert related[0]["score"] == 1.0

    products = client.get("/api/products", headers=headers)
    assert products.status_code == 200
    by_id = {p["id"]: p for p in products.json()}
    stored = by_id[ids[0]].get("related_products") or []
    assert any(r["product_id"] == ids[1] for r in stored)


def test_rematch_requires_target(client, auth_headers):
    res = client.post("/api/match/rematch", headers=auth_headers, json={})
    assert res.status_code == 422
