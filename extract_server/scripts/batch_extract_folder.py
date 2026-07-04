#!/usr/bin/env python3
"""Extract products from all images in a data batch folder and write per-image JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from grocery_extract.pipeline import extract_from_upload  # noqa: E402

IMAGE_SUFFIXES = {".heic", ".jpg", ".jpeg", ".png", ".webp"}


def extraction_to_json(result) -> dict:
    payload = result.model_dump(mode="json")
    payload["products"] = [product.to_product_dict() for product in result.products]
    return payload


def iter_images(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "folder",
        type=Path,
        help="Batch folder under grocery-prices/data (e.g. 2026_06_30)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip images that already have a sibling .json file",
    )
    args = parser.parse_args()

    folder = args.folder
    if not folder.is_absolute():
        folder = ROOT / "data" / folder.name if folder.parent == Path("data") else ROOT / folder
    folder = folder.resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 1

    images = iter_images(folder)
    if not images:
        print(f"No images found in {folder}", file=sys.stderr)
        return 1

    for index, image_path in enumerate(images, start=1):
        out_path = folder / f"{image_path.stem}.json"
        if args.skip_existing and out_path.exists():
            print(f"[{index}/{len(images)}] skip {image_path.name} (json exists)")
            continue

        print(f"[{index}/{len(images)}] extracting {image_path.name} ...", flush=True)
        result = extract_from_upload(image_path)
        payload = extraction_to_json(result)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(
            f"  -> {out_path.name}: {len(result.products)} products "
            f"({result.timing.llm_ms if result.timing else 0} ms llm)",
            flush=True,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
