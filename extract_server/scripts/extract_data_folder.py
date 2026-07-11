#!/usr/bin/env python3
"""Extract products from local data-folder images into sidecar JSON files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from extract_server.extraction.pipeline import extract_from_upload  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".webp", ".png"}


def _image_files(folder: Path) -> list[Path]:
    files = [
        path
        for path in sorted(folder.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    # Prefer jpg/jpeg over webp when both exist for the same stem.
    by_stem: dict[str, Path] = {}
    priority = {".jpg": 0, ".jpeg": 1, ".png": 2, ".webp": 3}
    for path in files:
        stem = path.stem
        existing = by_stem.get(stem)
        if existing is None or priority.get(path.suffix.lower(), 9) < priority.get(
            existing.suffix.lower(), 9
        ):
            by_stem[stem] = path
    return [by_stem[stem] for stem in sorted(by_stem)]


def _flat_product(product) -> dict:
    data = product.to_product_dict()
    other = data.pop("other", None)
    if isinstance(other, dict):
        data.update(other)
    return data


def _write_json(folder: Path, image_path: Path, result) -> Path:
    rel_source = f"data/{folder.name}/{image_path.name}"
    timing = result.timing
    llm_ms = timing.llm_ms if timing else 0
    other_ms = timing.other_ms if timing else 0
    payload = {
        "image_id": image_path.stem,
        "date_folder": folder.name,
        "source_file": rel_source,
        "photo_type": result.photo_type,
        "products": [_flat_product(product) for product in result.products],
        "raw_response": result.raw_response,
        "extractor": result.extractor,
        "timing": {
            "llm_ms": llm_ms,
            "duration_ms": llm_ms + other_ms,
            "model": timing.model if timing else None,
        },
    }
    out_path = folder / f"{image_path.stem}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    load_dotenv(REPO_ROOT / "extract_server" / ".env")
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "data" / "2026_07_06"
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 1

    images = _image_files(folder)
    if not images:
        print(f"No images found in {folder}", file=sys.stderr)
        return 1

    print(f"Extracting {len(images)} images from {folder}")
    for image_path in images:
        json_path = folder / f"{image_path.stem}.json"
        if json_path.exists():
            print(f"  skip {image_path.name} (json exists)")
            continue

        print(f"  extracting {image_path.name}...", flush=True)
        result = extract_from_upload(image_path)
        out_path = _write_json(folder, image_path, result)
        print(
            f"    -> {out_path.name} ({result.photo_type}, {len(result.products)} products, "
            f"{result.timing.llm_ms if result.timing else 0}ms)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
