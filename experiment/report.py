"""Aggregate experiment run metrics into summary reports."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _stdev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def confusion_matrix(runs: list[dict]) -> dict[str, dict[str, int]]:
    matrix = {
        "shelf": {"shelf": 0, "receipt": 0},
        "receipt": {"shelf": 0, "receipt": 0},
    }
    for run in runs:
        if run.get("error"):
            continue
        expected = run.get("expected_type")
        predicted = run.get("predicted_type")
        if expected in matrix and predicted in matrix[expected]:
            matrix[expected][predicted] += 1
    return matrix


def aggregate_approach(runs: list[dict], approach: str) -> dict[str, Any]:
    bucket = [r for r in runs if r.get("approach") == approach and not r.get("error")]
    if not bucket:
        return {"approach": approach, "runs": 0}

    type_correct = [1.0 if r.get("type_correct") else 0.0 for r in bucket]
    f1_all = [float(r["f1"]) for r in bucket]
    f1_correct = [float(r["f1"]) for r in bucket if r.get("type_correct")]
    price_acc = [float(r["price_accuracy"]) for r in bucket]
    total_llm_s = [float(r["total_llm_ms"]) / 1000 for r in bucket]

    shelf_runs = [r for r in bucket if r.get("expected_type") == "shelf"]
    receipt_runs = [r for r in bucket if r.get("expected_type") == "receipt"]

    return {
        "approach": approach,
        "runs": len(bucket),
        "type_accuracy": round(_mean(type_correct), 3),
        "mean_f1": round(_mean(f1_all), 3),
        "stdev_f1": round(_stdev(f1_all), 3),
        "mean_f1_type_correct": round(_mean(f1_correct), 3) if f1_correct else None,
        "mean_price_accuracy": round(_mean(price_acc), 3),
        "mean_total_llm_seconds": round(_mean(total_llm_s), 2),
        "stdev_total_llm_seconds": round(_stdev(total_llm_s), 2),
        "llm_calls": bucket[0].get("llm_calls"),
        "mean_shelf_f1": round(_mean([float(r["f1"]) for r in shelf_runs]), 3) if shelf_runs else None,
        "mean_receipt_f1": round(_mean([float(r["f1"]) for r in receipt_runs]), 3) if receipt_runs else None,
        "confusion_matrix": confusion_matrix(bucket),
    }


def build_summary(runs: list[dict], approaches: list[str]) -> dict[str, Any]:
    return {
        "total_runs": len(runs),
        "failed_runs": sum(1 for r in runs if r.get("error")),
        "by_approach": [aggregate_approach(runs, approach) for approach in approaches],
    }


def render_markdown(summary: dict[str, Any], config: dict[str, Any], out_dir: Path) -> str:
    lines = [
        "# Photo type experiment: 2-step vs 1-step",
        "",
        f"Output: `{out_dir}`",
        f"Subset: {config.get('subset')}",
        f"Backend: {config.get('backend')}",
        f"Model: {config.get('model')}",
        f"Scale: {config.get('scale_pct')}%",
        f"Repeats: {config.get('repeats')}",
        "",
        "| Approach | Type acc | F1 (all) | F1 (type correct) | Price acc | Total LLM s | Calls |",
        "|----------|----------|----------|-------------------|-----------|-------------|------:|",
    ]
    for row in summary["by_approach"]:
        if not row.get("runs"):
            continue
        f1_correct = row.get("mean_f1_type_correct")
        f1_correct_str = f"{f1_correct:.3f}" if f1_correct is not None else "n/a"
        lines.append(
            f"| {row['approach']} | {row['type_accuracy']} | {row['mean_f1']} "
            f"| {f1_correct_str} | {row['mean_price_accuracy']} "
            f"| {row['mean_total_llm_seconds']} ± {row['stdev_total_llm_seconds']} "
            f"| {row['llm_calls']} |"
        )

    lines.extend(["", "## Stratified F1", ""])
    for row in summary["by_approach"]:
        if not row.get("runs"):
            continue
        lines.append(
            f"- **{row['approach']}**: shelf F1={row.get('mean_shelf_f1', 'n/a')}, "
            f"receipt F1={row.get('mean_receipt_f1', 'n/a')}"
        )

    lines.extend(["", "## Classification confusion matrix", ""])
    for row in summary["by_approach"]:
        if row.get("approach") == "oracle" or not row.get("runs"):
            continue
        matrix = row.get("confusion_matrix", {})
        lines.extend(
            [
                f"### {row['approach']}",
                "",
                "|  | pred shelf | pred receipt |",
                "|--|-----------:|-------------:|",
                f"| actual shelf | {matrix.get('shelf', {}).get('shelf', 0)} | "
                f"{matrix.get('shelf', {}).get('receipt', 0)} |",
                f"| actual receipt | {matrix.get('receipt', {}).get('shelf', 0)} | "
                f"{matrix.get('receipt', {}).get('receipt', 0)} |",
                "",
            ]
        )

    lines.extend(["", "## Decision criteria", ""])
    lines.extend(
        [
            "Recommend 1-step in production if all of:",
            "1. End-to-end F1 within 2% of 2-step on full subset",
            "2. Type accuracy >= 2-step",
            "3. Total LLM latency meaningfully lower",
            "",
            "## Logs",
            "",
            "`logs/<image_id>/<approach>_repN`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_summary(
    runs: list[dict],
    approaches: list[str],
    config: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    summary = build_summary(runs, approaches)
    summary["config"] = config
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render_markdown(summary, config, out_dir))
    return summary
