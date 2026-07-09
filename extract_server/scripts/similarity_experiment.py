#!/usr/bin/env python3
"""Compare product similarity scorers against labeled pairs from data/ extractions."""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from extract_server.extraction.scoring import name_similarity, normalize_name

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

STOP_TOKENS = frozenset({
    "with", "and", "the", "a", "an", "of", "for", "in", "on", "w", "ea", "pkg", "pack",
    "value", "fresh", "food", "foods", "mart", "label", "superior", "bridge",
})

GENERIC_PRODUCT_TOKENS = frozenset({
    "rice", "ball", "balls", "pork", "soy", "sauce", "milk", "egg", "eggs", "tofu",
    "chips", "tomato", "tomatoes", "pasta", "frozen", "fresh", "boneless", "whole",
})


@dataclass(frozen=True)
class Product:
    product_name: str
    category: str = ""
    brand: str | None = None
    barcode: str | None = None
    image_id: str = ""
    date_folder: str = ""

    @property
    def key(self) -> str:
        return f"{self.date_folder}/{self.image_id}:{self.product_name}"


@dataclass(frozen=True)
class LabeledPair:
    a: Product
    b: Product
    label: int  # 1 = same product, 0 = different
    reason: str


Scorer = Callable[[Product, Product], float]


def tokenize(name: str) -> list[str]:
    return [t for t in normalize_name(name).split() if t and t not in STOP_TOKENS]


def token_jaccard(a: str, b: str, *, ignore_generic: bool = False) -> float:
    ta = {t for t in tokenize(a) if not (ignore_generic and t in GENERIC_PRODUCT_TOKENS)}
    tb = {t for t in tokenize(b) if not (ignore_generic and t in GENERIC_PRODUCT_TOKENS)}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def char_ngram_jaccard(a: str, b: str, n: int = 3) -> float:
    na, nb = normalize_name(a).replace(" ", ""), normalize_name(b).replace(" ", "")
    if len(na) < n or len(nb) < n:
        return 0.0
    ga = {na[i : i + n] for i in range(len(na) - n + 1)}
    gb = {nb[i : i + n] for i in range(len(nb) - n + 1)}
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def longest_common_substring_ratio(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    matcher = SequenceMatcher(None, na, nb)
    match = matcher.find_longest_match(0, len(na), 0, len(nb))
    lcs = match.size
    return (2 * lcs) / (len(na) + len(nb))


def barcode_score(a: Product, b: Product) -> float:
    if not a.barcode or not b.barcode:
        return 0.0
    return 1.0 if a.barcode == b.barcode else 0.0


def brand_match_score(a: Product, b: Product) -> float:
    if not a.brand or not b.brand:
        return 0.0
    return 1.0 if normalize_name(a.brand) == normalize_name(b.brand) else 0.0


def category_match_score(a: Product, b: Product) -> float:
    if not a.category or not b.category:
        return 0.0
    return 1.0 if normalize_name(a.category) == normalize_name(b.category) else 0.0


def composite_name_brand_category(a: Product, b: Product) -> float:
    name = name_similarity(a.product_name, b.product_name)
    brand = brand_match_score(a, b)
    category = category_match_score(a, b)
    return 0.72 * name + 0.18 * brand + 0.10 * category


def composite_with_barcode_boost(a: Product, b: Product) -> float:
    base = composite_name_brand_category(a, b)
    bc = barcode_score(a, b)
    if bc == 1.0:
        return max(base, 0.95)
    return base


def weighted_token_overlap(a: Product, b: Product) -> float:
    ta, tb = tokenize(a.product_name), tokenize(b.product_name)
    if not ta or not tb:
        return 0.0
    shared = set(ta) & set(tb)
    if not shared:
        return 0.0
    # Rare tokens count more than generic grocery words.
    weights = []
    for token in shared:
        weight = 1.0 if token in GENERIC_PRODUCT_TOKENS else 2.5
        weights.append(weight)
    overlap = sum(weights)
    denom = sum(2.5 if t not in GENERIC_PRODUCT_TOKENS else 1.0 for t in set(ta) | set(tb))
    return min(1.0, overlap / denom)


def scorer_sequence_matcher(a: Product, b: Product) -> float:
    return name_similarity(a.product_name, b.product_name)


def scorer_token_jaccard(a: Product, b: Product) -> float:
    return token_jaccard(a.product_name, b.product_name)


def scorer_token_jaccard_no_generic(a: Product, b: Product) -> float:
    return token_jaccard(a.product_name, b.product_name, ignore_generic=True)


def scorer_trigram_jaccard(a: Product, b: Product) -> float:
    return char_ngram_jaccard(a.product_name, b.product_name, n=3)


def scorer_lcs_ratio(a: Product, b: Product) -> float:
    return longest_common_substring_ratio(a.product_name, b.product_name)


def scorer_barcode_only(a: Product, b: Product) -> float:
    return barcode_score(a, b)


def scorer_composite(a: Product, b: Product) -> float:
    return composite_name_brand_category(a, b)


def scorer_composite_barcode(a: Product, b: Product) -> float:
    return composite_with_barcode_boost(a, b)


def scorer_weighted_tokens(a: Product, b: Product) -> float:
    return weighted_token_overlap(a, b)


def scorer_rapidfuzz_token_sort(a: Product, b: Product) -> float:
    return fuzz.token_sort_ratio(a.product_name, b.product_name) / 100


def scorer_rapidfuzz_wratio(a: Product, b: Product) -> float:
    return fuzz.WRatio(a.product_name, b.product_name) / 100


SCORERS: dict[str, Scorer] = {
    "sequence_matcher (current)": scorer_sequence_matcher,
    "token_jaccard": scorer_token_jaccard,
    "token_jaccard_no_generic": scorer_token_jaccard_no_generic,
    "trigram_jaccard": scorer_trigram_jaccard,
    "lcs_ratio": scorer_lcs_ratio,
    "weighted_token_overlap": scorer_weighted_tokens,
    "composite_name_brand_cat": scorer_composite,
    "composite_barcode_boost": scorer_composite_barcode,
    "barcode_only": scorer_barcode_only,
}

if HAS_RAPIDFUZZ:
    SCORERS["rapidfuzz_token_sort"] = scorer_rapidfuzz_token_sort
    SCORERS["rapidfuzz_wratio"] = scorer_rapidfuzz_wratio


def load_products() -> list[Product]:
    products: list[Product] = []
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.parent.name == "test-data":
            continue
        payload = json.loads(path.read_text())
        image_id = payload.get("image_id") or path.stem
        date_folder = payload.get("date_folder") or path.parent.name
        for item in payload.get("products", []):
            products.append(
                Product(
                    product_name=item.get("product_name", ""),
                    category=item.get("category", ""),
                    brand=item.get("brand"),
                    barcode=item.get("barcode"),
                    image_id=image_id,
                    date_folder=date_folder,
                )
            )
    return products


def build_labeled_pairs(products: list[Product]) -> list[LabeledPair]:
    pairs: list[LabeledPair] = []
    seen: set[tuple[str, str]] = set()

    def add(a: Product, b: Product, label: int, reason: str) -> None:
        if a.key == b.key:
            return
        key = tuple(sorted((a.key, b.key)))
        if key in seen:
            return
        seen.add(key)
        pairs.append(LabeledPair(a, b, label, reason))

    by_norm_name: dict[str, list[Product]] = defaultdict(list)
    by_barcode: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        by_norm_name[normalize_name(product.product_name)].append(product)
        if product.barcode:
            by_barcode[product.barcode].append(product)

    # Positives: exact normalized name across sightings.
    for group in by_norm_name.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                add(group[i], group[j], 1, "exact_normalized_name")

    # Positives: same barcode, likely same SKU (including mild name variants).
    for group in by_barcode.values():
        if len(group) < 2:
            continue
        names = {normalize_name(p.product_name) for p in group}
        if len(names) == 1:
            reason = "same_barcode_identical_name"
        else:
            reason = "same_barcode_name_variant"
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                add(group[i], group[j], 1, reason)

    # Manual positives: extraction variance for clearly same items.
    manual_positives = [
        (
            "Synear Rice Ball-BlackSesame",
            "思念 (Synear) Black Glutinous Rice Ball Sesame",
            "manual_synear_sesame_variant",
        ),
        (
            "VALUE PACK BONELESS PORK LOIN CENTRE CUT FAST FRY",
            "Value Pack Boneless Pork Loin Fast Fry Chops",
            "manual_pork_loin_variant",
        ),
        (
            "Pearl River Mushroom Dark Soy Sauce",
            "Pearl River Bridge Mushroom Flavoured Dark Soy Sauce",
            "manual_pearl_river_mushroom_soy",
        ),
        (
            "Pearl River Golden Soy Sauce",
            "Pearl River Bridge Golden Label Superior Light Soy Sauce",
            "manual_pearl_river_golden_light",
        ),
    ]
    by_exact_name = {p.product_name: p for p in products}
    for left, right, reason in manual_positives:
        if left in by_exact_name and right in by_exact_name:
            add(by_exact_name[left], by_exact_name[right], 1, reason)

    # Negatives: same brand + category, different product names.
    brand_cat_groups: dict[tuple[str, str], list[Product]] = defaultdict(list)
    for product in products:
        if product.brand:
            brand_cat_groups[(normalize_name(product.brand), normalize_name(product.category))].append(product)

    for group in brand_cat_groups.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if normalize_name(group[i].product_name) == normalize_name(group[j].product_name):
                    continue
                add(group[i], group[j], 0, "same_brand_category_diff_product")

    # Negatives: cross-category random sample (deterministic).
    categories = sorted({normalize_name(p.category) for p in products if p.category})
    cat_to_products: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        cat_to_products[normalize_name(product.category)].append(product)

    cross_count = 0
    for i, cat_a in enumerate(categories):
        for cat_b in categories[i + 1 :]:
            if cross_count >= 80:
                break
            a = cat_to_products[cat_a][cross_count % len(cat_to_products[cat_a])]
            b = cat_to_products[cat_b][cross_count % len(cat_to_products[cat_b])]
            add(a, b, 0, "cross_category")
            cross_count += 1

    # Negatives: similar product family but different flavor/SKU.
    family_negatives = [
        ("Spring Home Glutinous Rice Ball Red Bean Paste", "Spring Home Glutinous Rice Ball Sesame"),
        ("Spring Home Glutinous Rice Ball Sesame", "Spring Home Glutinous Rice Ball Peanut"),
        ("Pearl River Bridge Superior Dark Soy Sauce", "Pearl River Bridge Superior Light Soy Sauce"),
        ("Colgate Optic White Purple", "Colgate Optic White"),
        ("Colgate Sensitive Pro-Relief", "Colgate MaxFresh"),
        ("Sunrise Firm Tofu", "Sunrise Soft Tofu"),
        ("Beatrice 1% Milk", "Beatrice 2% Milk"),
        ("ItalPasta Spaghetti", "ItalPasta Linguine"),
    ]
    for left, right in family_negatives:
        if left in by_exact_name and right in by_exact_name:
            add(by_exact_name[left], by_exact_name[right], 0, "same_family_diff_sku")

    return pairs


def auc(scores: list[float], labels: list[int]) -> float:
    paired = sorted(zip(scores, labels), key=lambda x: x[0])
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    rank_sum = 0.0
    for idx, (_, label) in enumerate(paired, start=1):
        if label == 1:
            rank_sum += idx
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def evaluate(pairs: list[LabeledPair], scorer: Scorer, threshold: float = 0.55) -> dict[str, Any]:
    scores = [scorer(p.a, p.b) for p in pairs]
    labels = [p.label for p in pairs]

    tp = fp = tn = fn = 0
    for score, label in zip(scores, labels):
        pred = 1 if score >= threshold else 0
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    pos_scores = [s for s, y in zip(scores, labels) if y == 1]
    neg_scores = [s for s, y in zip(scores, labels) if y == 0]

    return {
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auc": auc(scores, labels),
        "pos_mean": statistics.mean(pos_scores) if pos_scores else 0.0,
        "neg_mean": statistics.mean(neg_scores) if neg_scores else 0.0,
        "separation": (statistics.mean(pos_scores) - statistics.mean(neg_scores)) if pos_scores and neg_scores else 0.0,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def best_threshold(pairs: list[LabeledPair], scorer: Scorer) -> float:
    scores = [scorer(p.a, p.b) for p in pairs]
    candidates = sorted(set(scores))
    if not candidates:
        return 0.55
    best_t, best_f1 = 0.55, -1.0
    for threshold in candidates:
        metrics = evaluate(pairs, scorer, threshold=threshold)
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_t = threshold
    return best_t


def top_failures(pairs: list[LabeledPair], scorer: Scorer, *, limit: int = 8) -> dict[str, list[dict[str, Any]]]:
    scored = [(scorer(p.a, p.b), p) for p in pairs]
    false_positives = sorted(
        [(s, p) for s, p in scored if p.label == 0],
        key=lambda x: -x[0],
    )[:limit]
    false_negatives = sorted(
        [(s, p) for s, p in scored if p.label == 1],
        key=lambda x: x[0],
    )[:limit]

    def row(score: float, pair: LabeledPair) -> dict[str, Any]:
        return {
            "score": round(score, 3),
            "reason": pair.reason,
            "a": pair.a.product_name,
            "b": pair.b.product_name,
            "barcodes": [pair.a.barcode, pair.b.barcode],
        }

    return {
        "false_positives": [row(s, p) for s, p in false_positives],
        "false_negatives": [row(s, p) for s, p in false_negatives],
    }


def dataset_summary(products: list[Product], pairs: list[LabeledPair]) -> dict[str, Any]:
    positives = [p for p in pairs if p.label == 1]
    negatives = [p for p in pairs if p.label == 0]
    reason_counts = Counter(p.reason for p in pairs)
    return {
        "product_count": len(products),
        "unique_normalized_names": len({normalize_name(p.product_name) for p in products}),
        "with_barcode": sum(1 for p in products if p.barcode),
        "pair_count": len(pairs),
        "positive_pairs": len(positives),
        "negative_pairs": len(negatives),
        "pair_reasons": dict(reason_counts.most_common()),
    }


def run() -> dict[str, Any]:
    products = load_products()
    pairs = build_labeled_pairs(products)
    text_only_pairs = [
        p for p in pairs
        if not (p.a.barcode and p.b.barcode)
    ]

    results: dict[str, Any] = {
        "dataset": dataset_summary(products, pairs),
        "scorers": {},
        "text_only_subset": {
            "pair_count": len(text_only_pairs),
            "positive_pairs": sum(1 for p in text_only_pairs if p.label == 1),
            "negative_pairs": sum(1 for p in text_only_pairs if p.label == 0),
        },
    }

    ranked: list[tuple[str, float, dict[str, Any]]] = []
    for name, scorer in SCORERS.items():
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
    return results


def print_report(results: dict[str, Any]) -> None:
    ds = results["dataset"]
    print("=" * 72)
    print("PRODUCT SIMILARITY EXPERIMENT")
    print("=" * 72)
    print(f"Products: {ds['product_count']} | Unique names: {ds['unique_normalized_names']} | With barcode: {ds['with_barcode']}")
    print(f"Labeled pairs: {ds['pair_count']} ({ds['positive_pairs']} positive, {ds['negative_pairs']} negative)")
    print("Pair reasons:", ", ".join(f"{k}={v}" for k, v in ds["pair_reasons"].items()))
    print()
    print(f"{'Scorer':<32} {'AUC':>6} {'Sep':>6} {'F1@.55':>7} {'BestF1':>7} {'TxtF1':>7}")
    print("-" * 72)
    for row in results["ranking_by_best_f1"]:
        name = row["scorer"]
        at_055 = results["scorers"][name]["at_threshold_0.55"]
        txt_f1 = results["scorers"][name].get("text_only_best_f1")
        txt_s = f"{txt_f1:>7.3f}" if txt_f1 is not None else "    n/a"
        print(
            f"{name:<32} {row['auc']:>6.3f} {row['separation']:>6.3f} "
            f"{at_055['f1']:>7.3f} {row['best_f1']:>7.3f}{txt_s}"
        )

    best = results["ranking_by_best_f1"][0]["scorer"]
    print()
    print(f"Best overall (by tuned F1): {best}")
    failures = results["scorers"][best]
    print("\nTop false positives:")
    for item in failures["top_false_positives"][:5]:
        print(f"  [{item['score']}] {item['a']!r} vs {item['b']!r} ({item['reason']})")
    print("\nTop false negatives:")
    for item in failures["top_false_negatives"][:5]:
        print(f"  [{item['score']}] {item['a']!r} vs {item['b']!r} ({item['reason']})")


if __name__ == "__main__":
    output = run()
    print_report(output)
    out_path = REPO_ROOT / "data" / "similarity_experiment_results.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {out_path.relative_to(REPO_ROOT)}")
