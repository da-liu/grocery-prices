from unittest.mock import patch
import uuid

import json
from fastapi.testclient import TestClient


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


def test_register_login_and_scoped_products(client, app):
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
    assert me.json()["token"] == token

    cookie_client = TestClient(app)
    cookie_client.cookies.set("grocery_session", token)
    me_cookie = cookie_client.get("/api/auth/me")
    assert me_cookie.status_code == 200
    assert me_cookie.json()["username"] == "testuser"
    assert me_cookie.json()["token"] == token

    unauth = client.get("/api/products")
    assert unauth.status_code == 401

    products = client.get("/api/products", headers={"Authorization": f"Bearer {token}"})
    assert products.status_code == 200
    assert products.json() == []


def test_upload_requires_auth(client):
    resp = client.post(
        "/api/photos/bulk",
        files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
    )
    assert resp.status_code == 401


def test_upload_with_mocked_ingest(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "uploader", "password": "password123"},
    )
    token = reg.json()["token"]

    with patch("server.accept_upload_batch") as ingest:
        ingest.return_value = [
            {
                "image_id": "IMG_0001",
                "image_path": "api/media/IMG_0001",
                "products": [],
                "product_count": 0,
                "meta": {},
                "extractor": None,
                "source": "upload",
                "extraction_status": "pending",
            }
        ]
        with patch.dict("os.environ", {"CURSOR_API_KEY": "test-key"}):
            resp = client.post(
                "/api/photos/bulk",
                headers={"Authorization": f"Bearer {token}"},
                files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
                data={"source": "upload"},
            )
    assert resp.status_code == 202
    assert resp.json()["results"][0]["image_id"] == "IMG_0001"
    assert resp.json()["results"][0]["extraction_status"] == "pending"


def test_upload_with_gemini_direct_backend_uses_google_key(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "gemini-uploader", "password": "password123"},
    )
    token = reg.json()["token"]
    captured: dict[str, object] = {}

    def fake_batch(paths, **kwargs):
        captured["api_key"] = kwargs["api_key"]
        return [
            {
                "image_id": "IMG_0001",
                "image_path": "api/media/IMG_0001",
                "products": [],
                "product_count": 0,
                "meta": {},
                "extractor": None,
                "source": "upload",
                "extraction_status": "pending",
            }
        ]

    with patch("server.accept_upload_batch", side_effect=fake_batch):
        with patch.dict(
            "os.environ",
            {
                "GROCERY_EXTRACT_BACKEND": "gemini_direct",
                "GOOGLE_API_KEY": "google-test-key",
            },
        ):
            resp = client.post(
                "/api/photos/bulk",
                headers={"Authorization": f"Bearer {token}"},
                files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
                data={"source": "upload"},
            )
    assert resp.status_code == 202
    assert captured["api_key"] == "google-test-key"


def test_rerun_extraction_with_gemini_direct_uses_google_key(client):
    reg = client.post(
        "/api/auth/register",
        json={"username": "gemini-reextract", "password": "password123"},
    )
    token = reg.json()["token"]

    with patch(
        "server.reextract_photo",
        return_value={
            "image_id": "IMG_0001",
            "products": [],
            "product_count": 0,
            "overlapping_products": [],
            "extraction_empty": True,
        },
    ) as reextract:
        with patch.dict(
            "os.environ",
            {
                "GROCERY_EXTRACT_BACKEND": "gemini_direct",
                "GOOGLE_API_KEY": "google-test-key",
            },
        ):
            resp = client.post(
                "/api/photos/IMG_0001/re-extract",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200
    assert reextract.call_args.kwargs["api_key"] == "google-test-key"


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


def test_store_location_snap_and_merge(client):
    username = f"stores_merge_{uuid.uuid4().hex[:8]}"
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        "/api/store-locations",
        headers=headers,
        json={
            "name": "Farm Boy",
            "latitude": 43.639428,
            "longitude": -79.380294,
            "match_radius_m": 150,
        },
    )
    assert first.status_code == 200, first.text
    first_store = first.json()
    assert first_store["matched_existing"] is False

    second = client.post(
        "/api/store-locations",
        headers=headers,
        json={
            "name": "Farm Boy Duplicate",
            "latitude": 43.639606,
            "longitude": -79.380394,
            "match_radius_m": 150,
        },
    )
    assert second.status_code == 200, second.text
    second_store = second.json()
    assert second_store["matched_existing"] is True
    assert second_store["id"] == first_store["id"]

    third = client.post(
        "/api/store-locations",
        headers=headers,
        json={
            "name": "Longos",
            "latitude": 43.642394,
            "longitude": -79.381181,
            "match_radius_m": 150,
        },
    )
    assert third.status_code == 200, third.text
    longos_id = third.json()["id"]

    merged = client.post(
        "/api/store-locations/merge",
        headers=headers,
        json={"source_id": longos_id, "target_id": first_store["id"]},
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["id"] == first_store["id"]

    listed = client.get("/api/store-locations", headers=headers)
    assert len(listed.json()) == 1
