from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any


def normalize_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", name)
    return " ".join(name.split())


def name_similarity(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.92
    return SequenceMatcher(None, na, nb).ratio()


def price_match(expected: Any, actual: Any, tol: float = 0.05) -> bool:
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    return abs(float(expected) - float(actual)) <= tol


def category_match(expected: str, actual: str) -> bool:
    return normalize_name(expected) == normalize_name(actual)


@dataclass
class ProductMatch:
    expected: dict[str, Any]
    actual: dict[str, Any] | None
    name_score: float = 0.0
    price_ok: bool = False
    category_ok: bool = False

    @property
    def matched(self) -> bool:
        return self.actual is not None and self.name_score >= 0.55 and self.price_ok


@dataclass
class ImageScore:
    image_id: str
    expected_count: int
    actual_count: int
    matches: list[ProductMatch] = field(default_factory=list)

    @property
    def recall(self) -> float:
        if not self.expected_count:
            return 1.0
        return sum(1 for m in self.matches if m.matched) / self.expected_count

    @property
    def precision(self) -> float:
        if not self.actual_count:
            return 1.0 if not self.expected_count else 0.0
        return sum(1 for m in self.matches if m.matched) / self.actual_count

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)

    @property
    def avg_name_score(self) -> float:
        matched = [m.name_score for m in self.matches if m.actual is not None]
        return sum(matched) / len(matched) if matched else 0.0


def score_image(image_id: str, expected: list[dict], actual: list[dict]) -> ImageScore:
    remaining = list(actual)
    matches: list[ProductMatch] = []

    for exp in expected:
        best_idx = -1
        best_name = 0.0
        for idx, act in enumerate(remaining):
            sim = name_similarity(exp.get("product_name", ""), act.get("product_name", ""))
            if sim > best_name:
                best_name = sim
                best_idx = idx
        if best_idx >= 0 and best_name >= 0.45:
            act = remaining.pop(best_idx)
            matches.append(
                ProductMatch(
                    expected=exp,
                    actual=act,
                    name_score=best_name,
                    price_ok=price_match(exp.get("price"), act.get("price")),
                    category_ok=category_match(exp.get("category", ""), act.get("category", "")),
                )
            )
        else:
            matches.append(ProductMatch(expected=exp, actual=None))

    for extra in remaining:
        matches.append(ProductMatch(expected={}, actual=extra))

    return ImageScore(
        image_id=image_id,
        expected_count=len(expected),
        actual_count=len(actual),
        matches=matches,
    )


@dataclass
class BenchmarkReport:
    image_scores: list[ImageScore]

    @property
    def mean_recall(self) -> float:
        if not self.image_scores:
            return 0.0
        return sum(s.recall for s in self.image_scores) / len(self.image_scores)

    @property
    def mean_precision(self) -> float:
        if not self.image_scores:
            return 0.0
        return sum(s.precision for s in self.image_scores) / len(self.image_scores)

    @property
    def mean_f1(self) -> float:
        if not self.image_scores:
            return 0.0
        return sum(s.f1 for s in self.image_scores) / len(self.image_scores)

    @property
    def price_accuracy(self) -> float:
        pairs = [
            m
            for s in self.image_scores
            for m in s.matches
            if m.actual is not None and m.expected
        ]
        if not pairs:
            return 0.0
        return sum(1 for m in pairs if m.price_ok) / len(pairs)

    @property
    def category_accuracy(self) -> float:
        pairs = [
            m
            for s in self.image_scores
            for m in s.matches
            if m.actual is not None and m.expected
        ]
        if not pairs:
            return 0.0
        return sum(1 for m in pairs if m.category_ok) / len(pairs)

    def summary(self) -> dict[str, float]:
        return {
            "mean_recall": round(self.mean_recall, 3),
            "mean_precision": round(self.mean_precision, 3),
            "mean_f1": round(self.mean_f1, 3),
            "price_accuracy": round(self.price_accuracy, 3),
            "category_accuracy": round(self.category_accuracy, 3),
            "images": len(self.image_scores),
        }


def benchmark(expected_by_image: dict[str, list[dict]], actual_by_image: dict[str, list[dict]]) -> BenchmarkReport:
    scores = [
        score_image(image_id, expected_by_image[image_id], actual_by_image.get(image_id, []))
        for image_id in sorted(expected_by_image)
    ]
    return BenchmarkReport(image_scores=scores)
