#!/usr/bin/env python3
"""Compare 2-step vs 1-step photo type classification and extraction."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract_server"))
sys.path.insert(0, str(ROOT / "extract_server" / "scripts"))

from experiment.approaches.one_step import run_one_step  # noqa: E402
from experiment.approaches.oracle import run_oracle  # noqa: E402
from experiment.approaches.two_step import run_two_step  # noqa: E402
from experiment.dataset import EvalImage, SubsetName, ground_truth_by_image, load_subset  # noqa: E402
from experiment.report import write_summary  # noqa: E402
from experiment.vision import default_model_for_backend  # noqa: E402
from experiment_common import score_run, utc_now, write_run_log  # noqa: E402

DEFAULT_APPROACHES = ["two_step", "one_step"]
VALID_APPROACHES = {"two_step", "one_step", "oracle"}


def _configure_env(backend: str, scale_pct: int) -> None:
    os.environ["GROCERY_EXTRACT_BACKEND"] = backend
    os.environ["GROCERY_EXTRACT_SCALE_PCT"] = str(scale_pct)


def _check_api_key(backend: str) -> bool:
    if backend == "gemini_direct":
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    return bool(os.environ.get("CURSOR_API_KEY"))


def _run_approach(
    approach: str,
    image: EvalImage,
    image_path: Path,
    *,
    backend: str,
    model: str,
    llm_scale_pct: int | None,
):
    if approach == "two_step":
        return run_two_step(image_path, backend=backend, model=model, llm_scale_pct=llm_scale_pct)
    if approach == "one_step":
        return run_one_step(
            image_path,
            backend=backend,
            model=model,
            llm_scale_pct=llm_scale_pct,
        )
    if approach == "oracle":
        return run_oracle(
            image_path,
            expected_type=image.expected_type,
            backend=backend,
            model=model,
            llm_scale_pct=llm_scale_pct,
        )
    raise ValueError(f"Unknown approach: {approach}")


def run_experiment(
    *,
    subset: SubsetName,
    approaches: list[str],
    backend: str,
    model: str,
    scale_pct: int,
    repeats: int,
    out_dir: Path,
) -> dict:
    _configure_env(backend, scale_pct)
    images = load_subset(subset)
    truth = ground_truth_by_image(images)
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"

    config = {
        "created_at": utc_now(),
        "experiment": "photo_type_two_step_vs_one_step",
        "subset": subset,
        "image_ids": [img.image_id for img in images],
        "approaches": approaches,
        "backend": backend,
        "model": model,
        "scale_pct": scale_pct,
        "repeats": repeats,
    }
    (out_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    runs: list[dict] = []
    total = len(images) * len(approaches) * repeats
    n = 0

    for image in images:
        file_kb = round(image.path.stat().st_size / 1024, 1)

        for approach in approaches:
            for repeat in range(1, repeats + 1):
                n += 1
                stem = f"{image.image_id}/{approach}_rep{repeat}"
                print(f"[{n}/{total}] {image.image_id} approach={approach} rep={repeat}", flush=True)

                record: dict = {
                    "image_id": image.image_id,
                    "expected_type": image.expected_type,
                    "approach": approach,
                    "backend": backend,
                    "model": model,
                    "repeat": repeat,
                    "scale_pct": scale_pct,
                    "file_kb": file_kb,
                }
                raw = ""
                try:
                    result = _run_approach(
                        approach,
                        image,
                        image.path,
                        backend=backend,
                        model=model,
                        llm_scale_pct=None,
                    )
                    raw = result.raw_response
                    record.update(score_run(image.image_id, result.products, truth))
                    record["predicted_type"] = result.predicted_type
                    record["type_correct"] = result.predicted_type == image.expected_type
                    record["end_to_end_f1"] = record["f1"]
                    record["classify_ms"] = result.classify_ms
                    record["extract_ms"] = result.extract_ms
                    record["total_llm_ms"] = result.total_llm_ms
                    record["llm_calls"] = result.llm_calls
                    record["products"] = result.products
                    record["error"] = None
                except Exception as err:
                    record["error"] = str(err)
                    record["predicted_type"] = None
                    record["type_correct"] = False
                    record["classify_ms"] = 0
                    record["extract_ms"] = 0
                    record["total_llm_ms"] = 0
                    record["llm_calls"] = 0
                    record["products"] = []
                    record.update(
                        {
                            "expected_count": len(truth.get(image.image_id, [])),
                            "product_count": 0,
                            "recall": 0,
                            "precision": 0,
                            "f1": 0,
                            "price_accuracy": 0,
                            "end_to_end_f1": 0,
                        }
                    )

                write_run_log(logs_dir, stem, record, raw)
                runs.append(record)

    return write_summary(runs, approaches, config, out_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare 2-step vs 1-step photo type handling")
    parser.add_argument("--approaches", nargs="+", default=DEFAULT_APPROACHES)
    parser.add_argument("--subset", choices=["quick", "default", "full"], default="default")
    parser.add_argument("--backend", choices=["cursor", "gemini_direct"], default="cursor")
    parser.add_argument("--model", default=None)
    parser.add_argument("--scale", type=int, default=25)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "experiment" / "results" / "latest",
    )
    args = parser.parse_args()

    invalid = set(args.approaches) - VALID_APPROACHES
    if invalid:
        print(f"Unknown approaches: {', '.join(sorted(invalid))}", file=sys.stderr)
        return 1

    if not _check_api_key(args.backend):
        key_name = "GEMINI_API_KEY/GOOGLE_API_KEY" if args.backend == "gemini_direct" else "CURSOR_API_KEY"
        print(f"{key_name} required", file=sys.stderr)
        return 1

    model = args.model or default_model_for_backend(args.backend)
    out_dir = args.out_dir
    if out_dir.name == "latest":
        out_dir = out_dir.parent / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    summary = run_experiment(
        subset=args.subset,
        approaches=args.approaches,
        backend=args.backend,
        model=model,
        scale_pct=args.scale,
        repeats=args.repeats,
        out_dir=out_dir,
    )
    print((out_dir / "summary.md").read_text())
    print(f"Wrote results to {out_dir}")
    return 0 if summary["failed_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
