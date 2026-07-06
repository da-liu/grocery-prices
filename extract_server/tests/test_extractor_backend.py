from __future__ import annotations

import base64
from pathlib import Path

from grocery_extract.cursor_extractor import (
    ExtractImageResult,
    default_extract_model,
    current_extractor_name,
    extract_products_from_image,
)
from grocery_extract.pipeline import extract_from_upload
from grocery_extract.schema import ExtractedProduct


def test_default_extract_model_uses_backend_defaults(monkeypatch):
    monkeypatch.setenv("GROCERY_EXTRACT_BACKEND", "gemini_direct")

    assert default_extract_model() == "gemini-3.1-flash-lite"
    assert current_extractor_name() == "gemini_direct"


def test_extract_products_from_image_posts_to_gemini_direct(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source-image")

    monkeypatch.setenv("GROCERY_EXTRACT_BACKEND", "gemini_direct")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"products":[{"product_name":"Milk","price":4.99,"category":"dairy"}]}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, *, params: dict, json: dict):
            captured["url"] = url
            captured["params"] = params
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("grocery_extract.cursor_extractor.httpx.Client", FakeClient)

    result = extract_products_from_image(source)

    assert result.products[0].product_name == "Milk"
    assert result.raw_response.startswith('{"products"')
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.1-flash-lite:generateContent"
    )
    assert captured["params"] == {"key": "google-key"}
    payload = captured["payload"]
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    encoded = payload["contents"][0]["parts"][1]["inline_data"]["data"]
    assert base64.b64decode(encoded) == b"source-image"


def test_extract_from_upload_uses_backend_extractor_label(tmp_path: Path, monkeypatch):
    upload = tmp_path / "photo.jpg"
    upload.write_bytes(b"jpg-bytes")

    monkeypatch.setattr(
        "grocery_extract.pipeline.extract_products_from_image",
        lambda *_args, **_kwargs: ExtractImageResult(
            products=[ExtractedProduct(product_name="Milk", price=4.99, category="dairy")],
            raw_response='{"products":[{"product_name":"Milk","price":4.99,"category":"dairy"}]}',
            prep_ms=1,
            llm_ms=2,
            model="gemini-3.1-flash-lite",
        ),
    )
    monkeypatch.setattr("grocery_extract.pipeline.current_extractor_name", lambda: "gemini_direct")

    result = extract_from_upload(
        upload,
        image_id="IMG_0001",
        api_key="test-key",
        exif={},
        skip_normalize=True,
    )

    assert result.extractor == "gemini_direct"
    assert len(result.products) == 1
