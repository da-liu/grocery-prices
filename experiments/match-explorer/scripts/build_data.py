#!/usr/bin/env python3
"""Build manifest.json for the match-explorer React app."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
PREVIEW_DIR = REPO_ROOT / ".tmp-jpg"
CACHE_PATH = DATA_DIR / "embedding_cache.json"
OUT_PATH = Path(__file__).resolve().parents[1] / "public" / "data" / "manifest.json"
EXPERIMENT_RESULTS_PATH = DATA_DIR / "similarity_experiment_llm_results.json"
EXPERIMENTAL_SCORER = "emb_0.6_rapidfuzz_0.4"
MIN_SCORE = 0.65

EMBED_KEY_PREFIX = "gemini_emb001_name_semantic|"
BROWSER_SUFFIXES = (".jpg", ".jpeg", ".webp")
HEIC_SUFFIXES = (".HEIC", ".heic")


def load_embedding(cache: dict[str, list[float]], product_name: str) -> list[float] | None:
    return cache.get(f"{EMBED_KEY_PREFIX}{product_name}")


def ensure_jpeg_preview(source: Path) -> Path | None:
    rel = source.relative_to(DATA_DIR)
    preview = PREVIEW_DIR / rel.with_suffix(".jpg")
    if preview.is_file() and preview.stat().st_mtime >= source.stat().st_mtime:
        return preview

    preview.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["sips", "-s", "format", "jpeg", str(source), "--out", str(preview)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Warning: failed to convert {source}: {result.stderr.strip()}", file=sys.stderr)
        return None
    return preview


def resolve_image_file(date_folder: str, image_id: str, payload: dict) -> str | None:
    image_path = payload.get("image_path")
    if isinstance(image_path, str) and image_path:
        candidate = REPO_ROOT / image_path
        if candidate.is_file() and candidate.suffix.lower() in {*BROWSER_SUFFIXES, ".png"}:
            try:
                return str(candidate.relative_to(DATA_DIR))
            except ValueError:
                pass

    folder = DATA_DIR / date_folder
    for ext in BROWSER_SUFFIXES:
        candidate = folder / f"{image_id}{ext}"
        if candidate.is_file():
            return f"{date_folder}/{image_id}{ext}"

    for ext in HEIC_SUFFIXES:
        candidate = folder / f"{image_id}{ext}"
        if candidate.is_file():
            preview = ensure_jpeg_preview(candidate)
            if preview is not None:
                return f"{date_folder}/{image_id}.jpg"

    return None


def load_experiment_metrics(scorer_name: str) -> dict | None:
    if not EXPERIMENT_RESULTS_PATH.is_file():
        return None
    payload = json.loads(EXPERIMENT_RESULTS_PATH.read_text())
    scorer = payload.get("scorers", {}).get(scorer_name)
    if not scorer:
        return None
    tuned = scorer.get("at_best_threshold") or {}
    at_min = scorer.get("at_threshold_0.55") or {}
    return {
        "best_f1": tuned.get("f1", 0.0),
        "best_threshold": scorer.get("best_threshold", 0.0),
        "auc": tuned.get("auc", 0.0),
        "separation": tuned.get("separation", 0.0),
        "f1_at_min_score": at_min.get("f1"),
    }


def main() -> None:
    if not CACHE_PATH.exists():
        print(f"Missing embedding cache: {CACHE_PATH}", file=sys.stderr)
        sys.exit(1)

    cache = json.loads(CACHE_PATH.read_text())
    photos: list[dict] = []
    products: list[dict] = []

    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.name in {"embedding_cache.json", "similarity_experiment_results.json", "similarity_experiment_llm_results.json"}:
            continue
        if path.parent.name == "test-data":
            continue

        payload = json.loads(path.read_text())
        meta = payload.get("meta") or {}
        image_id = meta.get("image_id") or path.stem
        date_folder = meta.get("date_folder") or path.parent.name

        photos.append(
            {
                "id": f"{date_folder}/{image_id}",
                "image_id": image_id,
                "date_folder": date_folder,
                "path": str(path.relative_to(REPO_ROOT)),
                "image_file": resolve_image_file(date_folder, image_id, payload),
                "meta": meta,
                "extraction": payload,
                "product_count": len(payload.get("products") or []),
            }
        )

        for idx, item in enumerate(payload.get("products") or []):
            product_id = f"{date_folder}/{image_id}#{idx}"
            name = item.get("product_name") or ""
            embedding = load_embedding(cache, name)
            products.append(
                {
                    "id": product_id,
                    "photo_id": f"{date_folder}/{image_id}",
                    "image_id": image_id,
                    "date_folder": date_folder,
                    "extraction_index": idx,
                    "product_name": name,
                    "category": item.get("category") or "",
                    "brand": item.get("brand"),
                    "barcode": item.get("barcode"),
                    "price": item.get("price"),
                    "embedding": embedding,
                }
            )

    experiment_metrics = load_experiment_metrics(EXPERIMENTAL_SCORER)

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "min_score": MIN_SCORE,
            "top_n": 5,
            "embed_model": "gemini-embedding-001",
            "default_scorer": "production",
            "scorers": {
                "production": {
                    "id": "production",
                    "label": "Production (0.75 emb + 0.25 Jaccard)",
                    "formula": "0.75 * embedding + 0.25 * token_jaccard",
                    "experiment": None,
                },
                "emb_rapidfuzz": {
                    "id": "emb_rapidfuzz",
                    "label": "Experiment (0.6 emb + 0.4 RapidFuzz)",
                    "formula": "0.6 * embedding + 0.4 * rapidfuzz WRatio",
                    "experiment": experiment_metrics,
                },
            },
        },
        "stats": {
            "photo_count": len(photos),
            "product_count": len(products),
            "with_embedding": sum(1 for p in products if p.get("embedding")),
            "with_image": sum(1 for p in photos if p.get("image_file")),
        },
        "photos": photos,
        "products": products,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(manifest, ensure_ascii=False) + "\n")
    print(f"Wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  {len(photos)} photos, {len(products)} products, {manifest['stats']['with_image']} viewable images")


if __name__ == "__main__":
    main()
