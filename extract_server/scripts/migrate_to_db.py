#!/usr/bin/env python3
"""One-time migration from JSON files to SQLite catalog tables."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extract_server.users_db import DB_PATH, _connect, init_db  # noqa: E402
from grocery_extract.catalog_db import (  # noqa: E402
    SIGHTING_COLUMNS,
    blob_keys,
    init_catalog_tables,
    photo_type_from_ingest_source,
)
from grocery_extract.exif import captured_at_from_exif, date_folder_from_exif
from grocery_extract.user_paths import DATA_DIR, user_extractions_dir, user_meta_path, user_root

LEGACY_ARTIFACTS = (".meta.json", "products.jsonl")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_product_fields(product: dict) -> tuple[str, str | None, float | None, dict]:
    product_name = str(product["product_name"])
    brand = product.get("brand")
    price = product.get("price")
    extras = {
        key: value
        for key, value in product.items()
        if key not in SIGHTING_COLUMNS and value is not None
    }
    if product.get("is_special") is False:
        extras.pop("is_special", None)
    return product_name, brand, price, extras


def _load_meta_by_stem(user_id: str) -> dict[str, dict]:
    path = user_meta_path(user_id)
    if not path.exists():
        return {}
    with path.open() as handle:
        return {Path(row["SourceFile"]).stem: row for row in json.load(handle)}


def _photos_roots(user_id: str) -> list[Path]:
    roots = [user_root(user_id) / "photos"]
    legacy = ROOT / "data" / "users" / user_id / "photos"
    if legacy.exists():
        roots.append(legacy)
    return roots


def _find_blob_keys(user_id: str, image_id: str, date_folder: str | None) -> tuple[str | None, str | None]:
    search_dirs: list[Path] = []
    for photos_root in _photos_roots(user_id):
        if not photos_root.exists():
            continue
        if date_folder:
            candidate = photos_root / date_folder
            if candidate.exists():
                search_dirs.append(candidate)
        search_dirs.extend(sorted(photos_root.glob("20*")))

    for batch_dir in search_dirs:
        for path in batch_dir.glob(f"{image_id}.*"):
            if path.suffix.lower() == ".jpg":
                continue
            folder = batch_dir.name
            return blob_keys(user_id, folder, image_id, original_suffix=path.suffix)
        jpg = batch_dir / "jpg" / f"{image_id}.jpg"
        if jpg.exists():
            folder = batch_dir.name
            return blob_keys(user_id, folder, image_id, original_suffix=".jpg")
    return None, None


def migrate_user(user_id: str, *, dry_run: bool) -> dict[str, int]:
    stats = {"photos": 0, "extractions": 0, "sightings": 0}
    extractions_dir = user_extractions_dir(user_id)
    if not extractions_dir.exists():
        return stats

    meta_by_stem = _load_meta_by_stem(user_id)
    now = _utc_now()

    with _connect() as conn:
        for path in sorted(extractions_dir.glob("IMG_*.json")):
            image_id = path.stem
            with path.open() as handle:
                payload = json.load(handle)

            meta = meta_by_stem.get(image_id, {})
            raw_dt = meta.get("DateTimeOriginal")
            captured_at = captured_at_from_exif(raw_dt)
            date_folder = date_folder_from_exif(raw_dt)
            original_key, photo_key = _find_blob_keys(user_id, image_id, date_folder)
            if photo_key is None:
                print(f"  skip {image_id}: jpeg blob not found")
                continue

            source = payload.get("source", "upload")
            photo_type = photo_type_from_ingest_source(source)
            store_location_id = meta.get("store_location_id")
            if isinstance(store_location_id, str) and not store_location_id:
                store_location_id = None

            if dry_run:
                stats["photos"] += 1
                stats["extractions"] += 1
                stats["sightings"] += len(payload.get("products", []))
                continue

            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR REPLACE INTO photos (
                    id, user_id, type, original_blob_key, photo_blob_key, content_hash,
                    gps_latitude, gps_longitude, captured_at, store_location_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    image_id,
                    user_id,
                    photo_type,
                    original_key,
                    photo_key,
                    meta.get("ContentHash"),
                    meta.get("GPSLatitude"),
                    meta.get("GPSLongitude"),
                    captured_at,
                    store_location_id,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO extractions (
                    user_id, photo_id, extractor, extracted_at, reextracted_at,
                    manually_edited_at, raw_response
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    image_id,
                    payload.get("extractor", "cursor_sdk"),
                    payload.get("extracted_at") or now,
                    payload.get("reextracted_at"),
                    payload.get("manually_edited_at"),
                    payload.get("raw_response"),
                ),
            )
            conn.execute(
                "DELETE FROM product_sightings WHERE user_id = ? AND photo_id = ?",
                (user_id, image_id),
            )
            for index, product in enumerate(payload.get("products", []), start=1):
                product_name, brand, price, extras = _split_product_fields(product)
                conn.execute(
                    """
                    INSERT INTO product_sightings (
                        id, user_id, photo_id, line_index, product_name, brand, price,
                        extras, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        user_id,
                        image_id,
                        index,
                        product_name,
                        brand,
                        price,
                        json.dumps(extras, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                stats["sightings"] += 1

            stats["photos"] += 1
            stats["extractions"] += 1
            conn.commit()

    return stats


def cleanup_legacy_files(user_id: str, *, dry_run: bool) -> None:
    user_dir = user_root(user_id)
    meta = user_dir / ".meta.json"
    products = user_dir / "products.jsonl"
    extractions = user_extractions_dir(user_id)

    for path in (meta, products):
        if path.exists():
            if dry_run:
                print(f"  would remove {path}")
            else:
                path.unlink()

    if extractions.exists():
        if dry_run:
            print(f"  would remove {extractions}")
        else:
            shutil.rmtree(extractions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", help="Migrate a single user id")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove legacy JSON artifacts after migration",
    )
    args = parser.parse_args()
    dry_run = not args.execute

    init_db()
    init_catalog_tables()

    users_dir = DATA_DIR / "users"
    if not users_dir.exists():
        print("No users directory found.")
        return 0

    user_ids = [args.user_id] if args.user_id else sorted(p.name for p in users_dir.iterdir() if p.is_dir())
    if dry_run:
        print("Dry run (pass --execute to apply)\n")

    total = {"photos": 0, "extractions": 0, "sightings": 0}
    for user_id in user_ids:
        print(f"User {user_id}")
        stats = migrate_user(user_id, dry_run=dry_run)
        for key in total:
            total[key] += stats[key]
        print(f"  photos={stats['photos']} extractions={stats['extractions']} sightings={stats['sightings']}")
        if args.cleanup and stats["photos"] > 0:
            cleanup_legacy_files(user_id, dry_run=dry_run)

    print(
        f"\nTotal: photos={total['photos']} extractions={total['extractions']} "
        f"sightings={total['sightings']}"
    )
    print(f"Database: {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
