from __future__ import annotations

import json
from pathlib import Path

from grocery_extract.products_builder import write_user_products_jsonl
from grocery_extract.user_paths import user_extractions_dir, user_meta_path, user_root


def parse_product_id(product_id: str) -> tuple[str, int] | None:
    if product_id.endswith("-empty"):
        image_id = product_id[: -len("-empty")]
        if image_id.startswith("IMG_"):
            return image_id, 0
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
    if idx == 0 and product_id.endswith("-empty"):
        return delete_photo(user_id, image_id)

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


def delete_products_bulk(user_id: str, product_ids: list[str]) -> dict:
    """Delete many products in one pass; rebuild products.jsonl once at the end."""
    deleted = 0
    photos_removed = 0
    failed: list[str] = []
    seen: set[str] = set()
    by_image: dict[str, list[tuple[str, int]]] = {}

    for product_id in product_ids:
        if product_id in seen:
            continue
        seen.add(product_id)
        parsed = parse_product_id(product_id)
        if parsed is None:
            failed.append(product_id)
            continue
        image_id, idx = parsed
        by_image.setdefault(image_id, []).append((product_id, idx))

    jsonl_dirty = False

    for image_id, items in by_image.items():
        empty_ids = [pid for pid, idx in items if idx == 0 and pid.endswith("-empty")]
        regular = [(pid, idx) for pid, idx in items if pid not in empty_ids]

        if empty_ids:
            if delete_photo(user_id, image_id):
                deleted += len(empty_ids)
                photos_removed += 1
                jsonl_dirty = True
            else:
                failed.extend(empty_ids)
            if regular:
                failed.extend(pid for pid, _ in regular)
            continue

        if not regular:
            continue

        extraction_path = user_extractions_dir(user_id) / f"{image_id}.json"
        if not extraction_path.exists():
            failed.extend(pid for pid, _ in regular)
            continue

        with extraction_path.open() as f:
            payload = json.load(f)

        products = payload.get("products", [])
        indices = sorted({idx - 1 for _, idx in regular if idx > 0}, reverse=True)
        removed_ids: list[str] = []
        not_found_ids: list[str] = []

        for product_index in indices:
            matched = [pid for pid, idx in regular if idx - 1 == product_index]
            if 0 <= product_index < len(products):
                products.pop(product_index)
                removed_ids.extend(matched)
            else:
                not_found_ids.extend(matched)

        failed.extend(not_found_ids)

        if removed_ids:
            deleted += len(removed_ids)
            if not products:
                if delete_photo(user_id, image_id):
                    photos_removed += 1
                else:
                    extraction_path.unlink(missing_ok=True)
                    _remove_meta(user_id, image_id)
                    photos_removed += 1
            else:
                payload["products"] = products
                extraction_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
                )
            jsonl_dirty = True

    if jsonl_dirty:
        write_user_products_jsonl(user_id)

    return {"deleted": deleted, "photos_removed": photos_removed, "failed": failed}
