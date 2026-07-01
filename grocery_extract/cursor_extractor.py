from __future__ import annotations

import os
from pathlib import Path

from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions, SDKImage, UserMessage

from grocery_extract.parse_response import parse_products_json
from grocery_extract.prompt import build_prompt, build_receipt_prompt
from grocery_extract.schema import ExtractedProduct

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = os.environ.get("GROCERY_EXTRACT_MODEL", "composer-2.5")


class CursorExtractError(RuntimeError):
    pass


def extract_products_from_image(
    image_path: Path,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    cwd: Path | None = None,
    prompt_variant: str = "shelf",
) -> tuple[list[ExtractedProduct], str]:
    """Extract products from a grocery photo using the Cursor SDK vision agent."""
    api_key = api_key or os.environ.get("CURSOR_API_KEY")
    if not api_key:
        raise CursorExtractError("CURSOR_API_KEY is required for Cursor SDK extraction")

    image_path = image_path.resolve()
    if not image_path.exists():
        raise CursorExtractError(f"Image not found: {image_path}")

    cwd = cwd or ROOT
    prompt = build_receipt_prompt() if prompt_variant == "receipt" else build_prompt()

    try:
        result = Agent.prompt(
            UserMessage(
                text=prompt,
                images=[SDKImage.from_file(str(image_path))],
            ),
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=str(cwd)),
            ),
        )
    except CursorAgentError as err:
        raise CursorExtractError(f"Cursor agent startup failed: {err.message}") from err

    if result.status == "error":
        raise CursorExtractError(f"Cursor agent run failed: {result.id}")

    raw = result.result or ""
    if not raw.strip():
        raise CursorExtractError("Empty response from Cursor agent")

    products = parse_products_json(raw)
    return products, raw
