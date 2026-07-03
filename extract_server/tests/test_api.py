import sys
from pathlib import Path
from unittest.mock import patch
import uuid

import json
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_health_requires_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["auth_required"] is True


def test_register_with_email(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "Alice@Example.com", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    assert reg.json()["username"] == "alice@example.com"

    login = client.post(
        "/api/auth/login",
        json={"username": "alice@example.com", "password": "password123"},
    )
    assert login.status_code == 200


def test_register_login_and_scoped_products(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    body = reg.json()
    assert body["username"] == "testuser"
    assert body["needs_onboarding"] is True
    token = body["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "testuser"

    unauth = client.get("/api/products")
    assert unauth.status_code == 401

    products = client.get("/api/products", headers={"Authorization": f"Bearer {token}"})
    assert products.status_code == 200
    assert products.json() == []


def test_upload_requires_auth(client):
    resp = client.post("/api/photos/upload", files={"file": ("x.jpg", b"abc", "image/jpeg")})
    assert resp.status_code == 401


def test_upload_with_mocked_ingest(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "uploader", "password": "password123"},
    )
    token = reg.json()["token"]

    with patch("server.ingest_upload") as ingest:
        ingest.return_value = {
            "image_id": "IMG_0001",
            "image_path": "api/media/IMG_0001",
            "products": [],
            "product_count": 0,
            "meta": {},
            "extractor": "cursor_sdk",
            "source": "upload",
        }
        resp = client.post(
            "/api/photos/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("x.jpg", b"abc", "image/jpeg")},
        )
    assert resp.status_code == 200
    assert resp.json()["image_id"] == "IMG_0001"


def test_delete_product(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "deleter", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    from extract_server.users_db import _connect
    from grocery_extract.products_builder import write_user_products_jsonl
    from grocery_extract.user_paths import user_extractions_dir

    with _connect() as conn:
        user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            ("deleter",),
        ).fetchone()["id"]

    extraction_dir = user_extractions_dir(user_id)
    extraction_dir.mkdir(parents=True, exist_ok=True)
    extraction_dir.joinpath("IMG_0001.json").write_text(
        json.dumps(
            {
                "image_id": "IMG_0001",
                "products": [
                    {"product_name": "Milk", "price": 5.99, "category": "dairy"},
                    {"product_name": "Bread", "price": 3.49, "category": "bakery"},
                ],
            }
        )
    )
    write_user_products_jsonl(user_id)

    products = client.get("/api/products", headers=headers).json()
    assert len(products) == 2

    delete = client.delete("/api/products/IMG_0001-1", headers=headers)
    assert delete.status_code == 200, delete.text

    products = client.get("/api/products", headers=headers).json()
    assert len(products) == 1
    assert products[0]["product_name"] == "Bread"


def test_bulk_delete_products(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "bulkdeleter", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    from extract_server.users_db import _connect
    from grocery_extract.products_builder import write_user_products_jsonl
    from grocery_extract.user_paths import user_extractions_dir

    with _connect() as conn:
        user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            ("bulkdeleter",),
        ).fetchone()["id"]

    extraction_dir = user_extractions_dir(user_id)
    extraction_dir.mkdir(parents=True, exist_ok=True)
    extraction_dir.joinpath("IMG_0001.json").write_text(
        json.dumps(
            {
                "image_id": "IMG_0001",
                "products": [
                    {"product_name": "Milk", "price": 5.99, "category": "dairy"},
                    {"product_name": "Bread", "price": 3.49, "category": "bakery"},
                ],
            }
        )
    )
    extraction_dir.joinpath("IMG_0002.json").write_text(
        json.dumps(
            {
                "image_id": "IMG_0002",
                "products": [
                    {"product_name": "Eggs", "price": 4.99, "category": "dairy"},
                ],
            }
        )
    )
    write_user_products_jsonl(user_id)

    bulk = client.post(
        "/api/products/bulk-delete",
        headers=headers,
        json={"ids": ["IMG_0001-1", "IMG_0001-2", "IMG_0002-1"]},
    )
    assert bulk.status_code == 200, bulk.text
    body = bulk.json()
    assert body["deleted"] == 3
    assert body["photos_removed"] == 2
    assert body["failed"] == []

    products = client.get("/api/products", headers=headers).json()
    assert products == []


def test_complete_onboarding(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "onboarded", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert reg.json()["needs_onboarding"] is True

    done = client.post("/api/auth/onboarding/complete", headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["needs_onboarding"] is False

    me = client.get("/api/auth/me", headers=headers)
    assert me.json()["needs_onboarding"] is False


def test_store_locations_crud(client):
    username = f"stores_{uuid.uuid4().hex[:8]}"
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    empty = client.get("/api/store-locations", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    created = client.post(
        "/api/store-locations",
        headers=headers,
        json={
            "name": "Test Market",
            "latitude": 43.65,
            "longitude": -79.38,
            "match_radius_m": 200,
        },
    )
    assert created.status_code == 200, created.text
    store = created.json()
    assert store["name"] == "Test Market"
    store_id = store["id"]

    listed = client.get("/api/store-locations", headers=headers)
    assert len(listed.json()) == 1

    updated = client.put(
        f"/api/store-locations/{store_id}",
        headers=headers,
        json={
            "name": "Test Market Updated",
            "latitude": 43.65,
            "longitude": -79.38,
            "match_radius_m": 250,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Test Market Updated"
    assert updated.json()["match_radius_m"] == 250

    deleted = client.delete(f"/api/store-locations/{store_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/api/store-locations", headers=headers).json() == []
