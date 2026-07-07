from __future__ import annotations

from unittest.mock import patch


def test_bulk_upload_accepts_exif_json(client, monkeypatch):
    reg = client.post(
        "/api/auth/register",
        json={"username": "exif-uploader", "password": "password123"},
    )
    token = reg.json()["token"]
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")

    captured: dict = {}

    def fake_batch(paths, **kwargs):
        captured["client_exifs"] = kwargs.get("client_exifs")
        return [
            {
                "image_id": "IMG_0001",
                "products": [],
                "product_count": 0,
                "meta": {},
                "extractor": "cursor_sdk",
                "extraction_status": "pending",
            }
        ]

    exif_payload = '[{"GPSLatitude":43.65,"GPSLongitude":-79.38,"captured_at":"2026-07-04T18:30:00-04:00","date_folder":"2026_07_04"}]'

    with patch("extract_server.routes.photos.accept_upload_batch", side_effect=fake_batch):
        resp = client.post(
            "/api/photos/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=[("files", ("image.jpg", b"photo-a", "image/jpeg"))],
            data={"exif_json": exif_payload},
        )

    assert resp.status_code == 202, resp.text
    assert captured["client_exifs"] == [
        {
            "GPSLatitude": 43.65,
            "GPSLongitude": -79.38,
            "captured_at": "2026-07-04T18:30:00-04:00",
            "date_folder": "2026_07_04",
        }
    ]


def test_bulk_upload_rejects_exif_json_length_mismatch(client, monkeypatch):
    reg = client.post(
        "/api/auth/register",
        json={"username": "exif-length", "password": "password123"},
    )
    token = reg.json()["token"]
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")

    resp = client.post(
        "/api/photos/bulk",
        headers={"Authorization": f"Bearer {token}"},
        files=[
            ("files", ("image-a.jpg", b"photo-a", "image/jpeg")),
            ("files", ("image-b.jpg", b"photo-b", "image/jpeg")),
        ],
        data={
            "exif_json": '[{"GPSLatitude":43.65,"GPSLongitude":-79.38,"DateTimeOriginal":"2026:07:04 18:30:00"}]',
        },
    )

    assert resp.status_code == 400
    assert "exif_json length" in resp.json()["detail"]
