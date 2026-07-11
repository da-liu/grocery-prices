#!/usr/bin/env python3
"""LLM embedding similarity experiments for grocery product matching."""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
from dotenv import load_dotenv

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from extract_server.extraction.matching import MatchSighting, score_pair  # noqa: E402

from similarity_experiment import (  # noqa: E402
    LabeledPair,
    Product,
    SCORERS as BASE_SCORERS,
    best_threshold,
    build_labeled_pairs,
    dataset_summary,
    evaluate,
    load_products,
    token_jaccard,
    top_failures,
)

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

EMB_RAPIDFUZZ_SCORER = "emb_0.6_rapidfuzz_0.4"
EMB_RAPIDFUZZ_EMB_WEIGHT = 0.6

REPO_ROOT = SCRIPTS_DIR.parents[1]
DATA_DIR = REPO_ROOT / "data"
CACHE_PATH = DATA_DIR / "embedding_cache.json"
RESULTS_PATH = DATA_DIR / "similarity_experiment_llm_results.json"

EMBED_BATCH_SIZE = 8
EMBED_DIM = 768


@dataclass(frozen=True)
class EmbeddingVariant:
    name: str
    model: str
    task_type: str | None = None
    text_fn: Callable[[Product], str] | None = None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def product_name_text(product: Product) -> str:
    return product.product_name


def product_structured_text(product: Product) -> str:
    parts = [f"product_name: {product.product_name}"]
    if product.brand:
        parts.append(f"brand: {product.brand}")
    if product.category:
        parts.append(f"category: {product.category}")
    if product.barcode:
        parts.append(f"barcode: {product.barcode}")
    return " | ".join(parts)


def gemini2_similarity_text(product: Product) -> str:
    return f"task: sentence similarity | query: {product_structured_text(product)}"


def gemini2_retrieval_document_text(product: Product) -> str:
    return f"task: search result | query: {product_structured_text(product)}"


EMBEDDING_VARIANTS: list[EmbeddingVariant] = [
    EmbeddingVariant(
        name="gemini_emb001_name_semantic",
        model="gemini-embedding-001",
        task_type="SEMANTIC_SIMILARITY",
        text_fn=product_name_text,
    ),
    EmbeddingVariant(
        name="gemini_emb001_structured_semantic",
        model="gemini-embedding-001",
        task_type="SEMANTIC_SIMILARITY",
        text_fn=product_structured_text,
    ),
    EmbeddingVariant(
        name="gemini_emb002_structured_similarity",
        model="gemini-embedding-2",
        task_type=None,
        text_fn=gemini2_similarity_text,
    ),
]


class EmbeddingClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = httpx.Client(timeout=60.0)

    def embed_batch(
        self,
        *,
        model: str,
        texts: list[str],
        task_type: str | None,
        max_retries: int = 6,
    ) -> list[list[float]]:
        if not texts:
            return []
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
        requests = []
        for text in texts:
            req: dict[str, Any] = {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBED_DIM,
            }
            if task_type:
                req["taskType"] = task_type
            requests.append(req)

        for attempt in range(max_retries):
            response = self.client.post(url, params={"key": self.api_key}, json={"requests": requests})
            if response.status_code == 200:
                payload = response.json()
                return [item["values"] for item in payload["embeddings"]]
            if response.status_code == 429 and attempt < max_retries - 1:
                wait_s = min(60.0, 5.0 * (2**attempt))
                retry_match = re.search(r"retry in ([0-9.]+)s", response.text, re.IGNORECASE)
                if retry_match:
                    wait_s = max(wait_s, float(retry_match.group(1)) + 1.0)
                print(f"    rate limited, waiting {wait_s:.0f}s...")
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"Embedding API {response.status_code}: {response.text[:500]}")
        raise RuntimeError("Embedding API retries exhausted")


def load_cache() -> dict[str, list[float]]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text())


def save_cache(cache: dict[str, list[float]]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False) + "\n")


def cache_key(variant: EmbeddingVariant, text: str) -> str:
    return f"{variant.name}|{text}"


def products_for_evaluation(products: list[Product], pairs: list[LabeledPair]) -> list[Product]:
    needed = {pair.a.key for pair in pairs} | {pair.b.key for pair in pairs}
    return [product for product in products if product.key in needed]


def embed_products(
    client: EmbeddingClient,
    products: list[Product],
    variant: EmbeddingVariant,
    cache: dict[str, list[float]],
) -> dict[str, list[float]]:
    text_by_key: dict[str, str] = {}
    for product in products:
        text = variant.text_fn(product) if variant.text_fn else product.product_name
        text_by_key[product.key] = text

    unique_texts = sorted(set(text_by_key.values()))
    missing = [text for text in unique_texts if cache_key(variant, text) not in cache]
    if missing:
        print(f"  Embedding {len(missing)} new texts for {variant.name}...")
        for start in range(0, len(missing), EMBED_BATCH_SIZE):
            batch = missing[start : start + EMBED_BATCH_SIZE]
            vectors = client.embed_batch(model=variant.model, texts=batch, task_type=variant.task_type)
            for text, vector in zip(batch, vectors):
                cache[cache_key(variant, text)] = vector
            save_cache(cache)
            time.sleep(1.0)

    return {
        product.key: cache[cache_key(variant, text_by_key[product.key])]
        for product in products
    }


def make_embedding_scorer(vectors: dict[str, list[float]]) -> Callable[[Product, Product], float]:
    def scorer(a: Product, b: Product) -> float:
        va = vectors.get(a.key)
        vb = vectors.get(b.key)
        if va is None or vb is None:
            return 0.0
        # Map cosine [-1, 1] to [0, 1] for threshold compatibility.
        return (cosine_similarity(va, vb) + 1.0) / 2.0

    return scorer


def product_to_sighting(product: Product) -> MatchSighting:
    return MatchSighting(
        id=product.key,
        photo_id=f"{product.date_folder}/{product.image_id}",
        product_name=product.product_name,
        category=product.category,
        brand=product.brand,
        barcode=product.barcode,
    )


def make_emb_rapidfuzz_scorer(
    vectors: dict[str, list[float]],
    *,
    emb_weight: float = EMB_RAPIDFUZZ_EMB_WEIGHT,
) -> Callable[[Product, Product], float]:
    base = make_embedding_scorer(vectors)

    def scorer(a: Product, b: Product) -> float:
        emb = base(a, b)
        if not HAS_RAPIDFUZZ:
            return emb
        rapidfuzz = fuzz.WRatio(a.product_name, b.product_name) / 100
        return emb_weight * emb + (1.0 - emb_weight) * rapidfuzz

    return scorer


def make_production_scorer(vectors: dict[str, list[float]]) -> Callable[[Product, Product], float]:
    def scorer(a: Product, b: Product) -> float:
        return score_pair(
            product_to_sighting(a),
            product_to_sighting(b),
            vector_a=vectors.get(a.key),
            vector_b=vectors.get(b.key),
        )

    return scorer


def make_hybrid_scorer(
    vectors: dict[str, list[float]],
    *,
    token_weight: float = 0.35,
    barcode_boost: bool = False,
) -> Callable[[Product, Product], float]:
    base = make_embedding_scorer(vectors)

    def scorer(a: Product, b: Product) -> float:
        emb = base(a, b)
        tok = token_jaccard(a.product_name, b.product_name, ignore_generic=True)
        score = (1.0 - token_weight) * emb + token_weight * tok
        if barcode_boost and a.barcode and b.barcode and a.barcode == b.barcode:
            return max(score, 0.95)
        return score

    return scorer


def run_llm_experiments() -> dict[str, Any]:
    load_dotenv(REPO_ROOT / "extract_server" / ".env")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for embedding experiments")

    products = load_products()
    pairs = build_labeled_pairs(products)
    eval_products = products_for_evaluation(products, pairs)
    text_only_pairs = [p for p in pairs if not (p.a.barcode and p.b.barcode)]

    client = EmbeddingClient(api_key)
    cache = load_cache()

    production_variant = EMBEDDING_VARIANTS[0]
    production_scorer_name = "production_matcher"

    results: dict[str, Any] = {
        "dataset": dataset_summary(products, pairs),
        "matching_config": {
            "production_scorer": production_scorer_name,
            "production_embedding_variant": production_variant.name,
        },
        "embedding_config": {
            "output_dimensionality": EMBED_DIM,
            "batch_size": EMBED_BATCH_SIZE,
            "cache_path": str(CACHE_PATH.relative_to(REPO_ROOT)),
        },
        "text_only_subset": {
            "pair_count": len(text_only_pairs),
            "positive_pairs": sum(1 for p in text_only_pairs if p.label == 1),
            "negative_pairs": sum(1 for p in text_only_pairs if p.label == 0),
        },
        "scorers": {},
        "baseline_scorers": {},
    }

    embedding_scorers: dict[str, Callable[[Product, Product], float]] = {}

    print("Embedding products...")
    for variant in EMBEDDING_VARIANTS:
        print(f"- {variant.name}")
        vectors = embed_products(client, eval_products, variant, cache)
        embedding_scorers[variant.name] = make_embedding_scorer(vectors)
        embedding_scorers[f"{variant.name}_x_token_jaccard"] = make_hybrid_scorer(vectors, token_weight=0.35)
        embedding_scorers[f"{variant.name}_composite_barcode"] = make_hybrid_scorer(
            vectors, token_weight=0.25, barcode_boost=True
        )
        if variant.name == production_variant.name:
            embedding_scorers[production_scorer_name] = make_production_scorer(vectors)
            embedding_scorers[EMB_RAPIDFUZZ_SCORER] = make_emb_rapidfuzz_scorer(vectors)

    # Evaluate embedding scorers.
    ranked: list[tuple[str, float, dict[str, Any]]] = []
    for name, scorer in embedding_scorers.items():
        tuned_threshold = best_threshold(pairs, scorer)
        at_055 = evaluate(pairs, scorer, threshold=0.55)
        tuned = evaluate(pairs, scorer, threshold=tuned_threshold)
        failures = top_failures(pairs, scorer)
        payload = {
            "at_threshold_0.55": {k: round(v, 3) if isinstance(v, float) else v for k, v in at_055.items()},
            "best_threshold": round(tuned_threshold, 3),
            "at_best_threshold": {k: round(v, 3) if isinstance(v, float) else v for k, v in tuned.items()},
            "text_only_best_f1": round(
                evaluate(text_only_pairs, scorer, threshold=best_threshold(text_only_pairs, scorer))["f1"], 3
            ) if text_only_pairs else None,
            "top_false_positives": failures["false_positives"],
            "top_false_negatives": failures["false_negatives"],
        }
        results["scorers"][name] = payload
        ranked.append((name, tuned["f1"], tuned))

    ranked.sort(key=lambda x: (-x[1], -x[2]["separation"]))
    results["ranking_by_best_f1"] = [
        {
            "scorer": name,
            "best_f1": round(metrics["f1"], 3),
            "best_threshold": round(metrics["threshold"], 3),
            "auc": round(metrics["auc"], 3),
            "separation": round(metrics["separation"], 3),
        }
        for name, _, metrics in ranked
    ]

    # Include a few non-embedding baselines for side-by-side comparison.
    baseline_names = [
        "token_jaccard",
        "composite_barcode_boost",
        "rapidfuzz_wratio",
        "sequence_matcher (current)",
    ]
    for name in baseline_names:
        scorer = BASE_SCORERS.get(name)
        if scorer is None:
            continue
        tuned_threshold = best_threshold(pairs, scorer)
        tuned = evaluate(pairs, scorer, threshold=tuned_threshold)
        results["baseline_scorers"][name] = {
            "best_threshold": round(tuned_threshold, 3),
            "best_f1": round(tuned["f1"], 3),
            "auc": round(tuned["auc"], 3),
            "separation": round(tuned["separation"], 3),
        }

    # Spot-check table on illustrative pairs.
    spot_pairs = [
        ("Synear Rice Ball-BlackSesame", "思念 (Synear) Black Glutinous Rice Ball Sesame", "same product"),
        ("Colgate Optic White Purple", "Colgate Optic White", "diff sku"),
        ("Pearl River Bridge Superior Dark Soy Sauce", "Pearl River Bridge Superior Light Soy Sauce", "diff sku"),
        ("Spring Home Glutinous Rice Ball Red Bean Paste", "Spring Home Glutinous Rice Ball Sesame", "diff flavor"),
        ("Thyme", "Colgate Total", "cross category"),
    ]
    by_name = {p.product_name: p for p in products}
    spot_checks: list[dict[str, Any]] = []
    for left, right, label in spot_pairs:
        if left not in by_name or right not in by_name:
            continue
        a, b = by_name[left], by_name[right]
        row: dict[str, Any] = {"label": label, "a": left, "b": right, "scores": {}}
        for name in [
            production_scorer_name,
            EMB_RAPIDFUZZ_SCORER,
            "gemini_emb001_name_semantic",
            "gemini_emb001_structured_semantic",
            "gemini_emb002_structured_similarity",
            "gemini_emb001_name_semantic_x_token_jaccard",
            "gemini_emb001_name_semantic_composite_barcode",
            "token_jaccard",
        ]:
            scorer = embedding_scorers.get(name) or BASE_SCORERS.get(name)
            if scorer:
                row["scores"][name] = round(scorer(a, b), 3)
        spot_checks.append(row)
    results["spot_checks"] = spot_checks

    return results


def print_report(results: dict[str, Any]) -> None:
    ds = results["dataset"]
    print("=" * 80)
    print("LLM EMBEDDING SIMILARITY EXPERIMENT")
    print("=" * 80)
    matching = results.get("matching_config", {})
    print(
        f"Products: {ds['product_count']} | Labeled pairs: {ds['pair_count']} "
        f"({ds['positive_pairs']}+ / {ds['negative_pairs']}-) | dim={results['embedding_config']['output_dimensionality']}"
    )
    print(f"Production scorer: {matching.get('production_scorer', 'production_matcher')}")
    print()
    print(f"{'Scorer':<44} {'AUC':>6} {'Sep':>6} {'F1@.55':>7} {'BestF1':>7} {'TxtF1':>7}")
    print("-" * 80)
    for row in results["ranking_by_best_f1"]:
        name = row["scorer"]
        at_055 = results["scorers"][name]["at_threshold_0.55"]
        txt_f1 = results["scorers"][name].get("text_only_best_f1")
        txt_s = f"{txt_f1:>7.3f}" if txt_f1 is not None else "    n/a"
        print(
            f"{name:<44} {row['auc']:>6.3f} {row['separation']:>6.3f} "
            f"{at_055['f1']:>7.3f} {row['best_f1']:>7.3f}{txt_s}"
        )

    print("\nNon-embedding baselines:")
    for name, metrics in results["baseline_scorers"].items():
        print(f"  {name:<32} AUC={metrics['auc']:.3f} F1={metrics['best_f1']:.3f}")

    print("\nSpot checks:")
    for row in results.get("spot_checks", []):
        print(f"\n[{row['label']}] {row['a'][:45]} <-> {row['b'][:45]}")
        for scorer, score in row["scores"].items():
            print(f"  {scorer:<44} {score:.3f}")

    if results["ranking_by_best_f1"]:
        best = results["ranking_by_best_f1"][0]["scorer"]
        print(f"\nBest embedding scorer (tuned F1): {best}")


if __name__ == "__main__":
    output = run_llm_experiments()
    print_report(output)
    RESULTS_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {RESULTS_PATH.relative_to(REPO_ROOT)}")
