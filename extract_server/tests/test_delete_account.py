from __future__ import annotations

import json
from pathlib import Path

from extract_server.db import get_conn, get_user_by_id, save_photo
from extract_server.extraction.paths import user_root


def _register(client, username: str = "delete-me", password: str = "password123"):
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert reg.status_code == 200, reg.text
    return reg.json()["token"], password


def _user_id(username: str) -> str:
    row = get_conn().execute(
        "SELECT id FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    assert row is not None
    return row["id"]


def _delete_account(client, token: str, password: str):
    return client.request(
        "DELETE",
        "/api/auth/account",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        content=json.dumps({"password": password}),
    )


def test_delete_account_removes_user_and_files(client):
    token, password = _register(client)
    user_id = _user_id("delete-me")

    photos_dir = user_root(user_id) / "photos" / "2026_07_12"
    photos_dir.mkdir(parents=True)
    (photos_dir / "IMG_0001.webp").write_bytes(b"webp")
    save_photo(
        user_id,
        photo_id="IMG_0001",
        blob_key=f"users/{user_id}/photos/2026_07_12/IMG_0001.webp",
        content_hash=None,
        gps_latitude=None,
        gps_longitude=None,
        captured_at="2026-07-12T12:00:00-04:00",
        store_location_id=None,
    )

    resp = _delete_account(client, token, password)
    assert resp.status_code == 204, resp.text
    assert get_user_by_id(user_id) is None
    assert not Path(user_root(user_id)).exists()

    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_after.status_code == 401


def test_delete_account_wrong_password_keeps_user(client):
    token, _password = _register(client, username="keep-me", password="password123")
    user_id = _user_id("keep-me")

    resp = _delete_account(client, token, "wrong-password")
    assert resp.status_code == 401
    assert get_user_by_id(user_id) is not None

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
