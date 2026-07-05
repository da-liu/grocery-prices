#!/usr/bin/env python3
"""Summarize extraction timing metrics from the grocery catalog database."""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract_server"))

from extract_server.users_db import _connect, init_db  # noqa: E402
from grocery_extract.logging_config import configure_cli_logging  # noqa: E402


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def _format_ms(ms: float | None) -> str:
    if ms is None:
        return "-"
    return f"{ms / 1000:.1f}s"


def _fetch_rows(days: int | None) -> list[dict]:
    cutoff = None
    if days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = """
        SELECT e.photo_id, e.extractor, e.duration_ms, e.prep_ms, e.llm_ms, e.classify_ms,
               e.queue_wait_ms, e.total_ms, e.model, e.photo_type, e.product_count,
               e.extracted_at, p.extraction_status
        FROM extractions e
        JOIN photos p ON p.user_id = e.user_id AND p.id = e.photo_id
    """
    params: tuple = ()
    if cutoff is not None:
        query += " WHERE e.extracted_at >= ?"
        params = (cutoff,)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _summarize(values: list[int | None]) -> dict[str, float | int]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"count": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0}
    return {
        "count": len(clean),
        "mean": statistics.mean(clean),
        "p50": _percentile(clean, 50),
        "p95": _percentile(clean, 95),
    }


def _print_metric_block(title: str, rows: list[dict], field: str) -> None:
    summary = _summarize([row.get(field) for row in rows])
    if summary["count"] == 0:
        return
    print(
        f"  {title:<14} mean={_format_ms(summary['mean'])} "
        f"p50={_format_ms(summary['p50'])} p95={_format_ms(summary['p95'])} "
        f"(n={summary['count']})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Limit to recent extractions (default: 7)")
    parser.add_argument("--all", action="store_true", help="Include all extractions regardless of age")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    configure_cli_logging(verbose=args.verbose)

    if not os.environ.get("GROCERY_DB_PATH"):
        print("GROCERY_DB_PATH is not set", file=sys.stderr)
        return 1

    init_db()
    rows = _fetch_rows(None if args.all else args.days)
    timed = [row for row in rows if row.get("duration_ms") is not None]
    failed = [row for row in rows if row.get("extraction_status") == "failed"]

    print(f"Extractions: {len(rows)} total, {len(timed)} with timing, {len(failed)} failed")
    if not timed:
        print("No timed extractions found.")
        return 0

    print("\nOverall")
    _print_metric_block("extract", timed, "duration_ms")
    _print_metric_block("llm", timed, "llm_ms")
    _print_metric_block("prep", timed, "prep_ms")
    _print_metric_block("queue wait", timed, "queue_wait_ms")
    _print_metric_block("total", timed, "total_ms")
    _print_metric_block("classify", timed, "classify_ms")

    by_model: dict[str, list[dict]] = {}
    for row in timed:
        model = row.get("model") or row.get("extractor") or "unknown"
        by_model.setdefault(model, []).append(row)

    print("\nBy model")
    for model, bucket in sorted(by_model.items()):
        summary = _summarize([row.get("llm_ms") for row in bucket])
        print(
            f"  {model:<20} llm p50={_format_ms(summary['p50'])} "
            f"p95={_format_ms(summary['p95'])} (n={summary['count']})"
        )

    by_type: dict[str, list[dict]] = {}
    for row in timed:
        photo_type = row.get("photo_type") or "unknown"
        by_type.setdefault(photo_type, []).append(row)

    print("\nBy photo type")
    for photo_type, bucket in sorted(by_type.items()):
        summary = _summarize([row.get("total_ms") for row in bucket])
        if summary["count"] == 0:
            summary = _summarize([row.get("duration_ms") for row in bucket])
        if summary["count"] == 0:
            continue
        print(
            f"  {photo_type:<10} total p50={_format_ms(summary['p50'])} "
            f"p95={_format_ms(summary['p95'])} (n={summary['count']})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
