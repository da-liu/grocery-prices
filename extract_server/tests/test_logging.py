from __future__ import annotations

import logging
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_request_id_header(client):
    resp = client.get("/health", headers={"X-Request-ID": "test-req-123"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "test-req-123"


def test_unhandled_exception_returns_generic_500(app):
    @app.get("/test-boom")
    def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/test-boom")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert "X-Request-ID" in resp.headers


def test_config_error_returns_safe_503(client):
    username = f"config_{uuid.uuid4().hex[:8]}"
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password123"},
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("extract_server.extract_config.configured_api_key", side_effect=ConfigError("CURSOR_API_KEY missing")):
        resp = client.post(
            "/api/photos/bulk",
            headers=headers,
            files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
        )
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Extraction unavailable"}


def test_extraction_error_returns_safe_502(client):
    from grocery_extract.errors import ExtractionError

    username = f"extract_{uuid.uuid4().hex[:8]}"
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "password": "password123"},
    )
    token = reg.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("extract_server.extract_config.configured_api_key", return_value="test-key"):
        with patch("extract_server.routes.photos.accept_upload_batch", side_effect=ExtractionError("LLM timeout")):
            resp = client.post(
                "/api/photos/bulk",
                headers=headers,
                files=[("files", ("x.jpg", b"abc", "image/jpeg"))],
            )
    assert resp.status_code == 502
    assert resp.json() == {"detail": "Extraction failed"}


def test_run_extraction_failure_logs(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setattr("grocery_extract.user_paths.ROOT", tmp_path)
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    from extract_server.users_db import init_db, register_user
    from grocery_extract.extract_worker import ExtractionJob
    from grocery_extract.ingest import accept_upload_batch, run_extraction

    caplog.set_level(logging.ERROR)

    init_db()
    user = register_user(f"log_{uuid.uuid4().hex[:8]}", "password12345")
    upload = tmp_path / "photo.webp"
    upload.write_bytes(b"RIFF....WEBP")

    monkeypatch.setattr("grocery_extract.user_stores_db.list_user_stores_as_dicts", lambda *_args: [])
    monkeypatch.setattr("grocery_extract.ingest.image_needs_store_label", lambda *_args: False)
    monkeypatch.setattr(
        "grocery_extract.ingest.extract_from_upload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mock llm failure")),
    )

    accepted = accept_upload_batch([upload], user_id=user.id, enqueue=False)[0]
    job = ExtractionJob(
        user_id=user.id,
        image_id=accepted["image_id"],
        api_key="test",
        user_stores=[],
        exif={},
        date_folder=accepted["date_folder"],
        captured_at=None,
        store_location_id=None,
        content_hash=accepted["content_hash"],
        request_id="req-log-test",
    )

    result = run_extraction(job)
    assert result["extraction_status"] == "failed"
    assert any("extraction_failed" in record.message for record in caplog.records)


# Import after test module load so server patches resolve correctly.
from grocery_extract.errors import ConfigError  # noqa: E402
