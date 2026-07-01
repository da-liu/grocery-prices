from __future__ import annotations

import json
from pathlib import Path

from grocery_extract.products_builder import write_user_products_jsonl
from grocery_extract.user_paths import user_extractions_dir, user_meta_path, user_root


def parse_product_id(product_id: str) -> tuple[str, int] | None:
    if "-" not in product_id:
        return None
    image_id, idx_str = product_id.rsplit("-", 1)
    if not image_id.startswith("IMG_") or not idx_str.isdigit():
        return None
    return image_id, int(idx_str)


def _load_meta_rows(user_id: str) -> list[dict]:
    path = user_meta_path(user_id)
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def _save_meta_rows(user_id: str, rows: list[dict]) -> None:
    path = user_meta_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")


def _remove_meta(user_id: str, image_id: str) -> None:
    rows = [row for row in _load_meta_rows(user_id) if Path(row["SourceFile"]).stem != image_id]
    _save_meta_rows(user_id, rows)


def delete_photo(user_id: str, image_id: str) -> bool:
    if not image_id.startswith("IMG_"):
        return False

    extraction_path = user_extractions_dir(user_id) / f"{image_id}.json"
    found = extraction_path.exists()

    photos_root = user_root(user_id) / "photos"
    if photos_root.exists():
        for batch_dir in photos_root.glob("20*"):
            for path in batch_dir.glob(f"{image_id}.*"):
                path.unlink(missing_ok=True)
                found = True
            jpg = batch_dir / "jpg" / f"{image_id}.jpg"
            if jpg.exists():
                jpg.unlink()
                found = True

    if extraction_path.exists():
        extraction_path.unlink()
        found = True

    if not found:
        return False

    _remove_meta(user_id, image_id)
    write_user_products_jsonl(user_id)
    return True


def delete_product(user_id: str, product_id: str) -> bool:
    parsed = parse_product_id(product_id)
    if parsed is None:
        return False

    image_id, idx = parsed
    extraction_path = user_extractions_dir(user_id) / f"{image_id}.json"
    if not extraction_path.exists():
        return False

    with extraction_path.open() as f:
        payload = json.load(f)

    products = payload.get("products", [])
    product_index = idx - 1
    if product_index < 0 or product_index >= len(products):
        return False

    products.pop(product_index)
    if not products:
        return delete_photo(user_id, image_id)

    payload["products"] = products
    extraction_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    write_user_products_jsonl(user_id)
    return True
