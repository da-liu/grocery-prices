from __future__ import annotations

import base64
from pathlib import Path

from extract_server.extraction.gemini_extractor import (
    ExtractImageResult,
    default_extract_model,
    current_extractor_name,
    extract_products_from_image,
)
from extract_server.extraction.pipeline import extract_from_upload
from extract_server.extraction.schema import ExtractedProduct


def test_default_extract_model_is_gemini():
    assert default_extract_model() == "gemini-3.1-flash-lite"
    assert current_extractor_name() == "gemini_direct"


def test_extract_products_from_image_posts_to_gemini(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source-image")

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")

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
                                        '{"type":"shelf","products":[{"product_name":"Milk","price":4.99,"category":"dairy"}]}'
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

    monkeypatch.setattr("extract_server.extraction.gemini_extractor.httpx.Client", FakeClient)

    result = extract_products_from_image(source)

    assert result.products[0].product_name == "Milk"
    assert result.photo_type == "shelf"
    assert result.raw_response.startswith('{"type"')
    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.1-flash-lite:generateContent"
    )
    assert captured["params"] == {"key": "gemini-key"}
    payload = captured["payload"]
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    encoded = payload["contents"][0]["parts"][1]["inline_data"]["data"]
    assert base64.b64decode(encoded) == b"source-image"


def test_extract_from_upload_uses_gemini_extractor_label(tmp_path: Path, monkeypatch):
    upload = tmp_path / "photo.jpg"
    upload.write_bytes(b"jpg-bytes")

    monkeypatch.setattr(
        "extract_server.extraction.pipeline.extract_products_from_image",
        lambda *_args, **_kwargs: ExtractImageResult(
            products=[ExtractedProduct(product_name="Milk", price=4.99, category="dairy")],
            photo_type="shelf",
            raw_response='{"type":"shelf","products":[{"product_name":"Milk","price":4.99,"category":"dairy"}]}',
            llm_ms=2,
            other_ms=1,
            model="gemini-3.1-flash-lite",
        ),
    )

    result = extract_from_upload(
        upload,
        api_key="test-key",
    )

    assert result.extractor == "gemini_direct"
    assert len(result.products) == 1
    assert result.photo_type == "shelf"
