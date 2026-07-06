from __future__ import annotations

from experiment.report import aggregate_approach, build_summary, confusion_matrix


def test_confusion_matrix():
    runs = [
        {"expected_type": "shelf", "predicted_type": "shelf"},
        {"expected_type": "shelf", "predicted_type": "receipt"},
        {"expected_type": "receipt", "predicted_type": "receipt"},
        {"expected_type": "receipt", "predicted_type": "shelf"},
    ]
    matrix = confusion_matrix(runs)
    assert matrix["shelf"]["shelf"] == 1
    assert matrix["shelf"]["receipt"] == 1
    assert matrix["receipt"]["receipt"] == 1
    assert matrix["receipt"]["shelf"] == 1


def test_aggregate_approach():
    runs = [
        {
            "approach": "one_step",
            "expected_type": "shelf",
            "predicted_type": "shelf",
            "type_correct": True,
            "f1": 0.8,
            "price_accuracy": 0.9,
            "total_llm_ms": 1000,
            "llm_calls": 1,
        },
        {
            "approach": "one_step",
            "expected_type": "receipt",
            "predicted_type": "shelf",
            "type_correct": False,
            "f1": 0.2,
            "price_accuracy": 0.5,
            "total_llm_ms": 1200,
            "llm_calls": 1,
        },
    ]
    row = aggregate_approach(runs, "one_step")
    assert row["runs"] == 2
    assert row["type_accuracy"] == 0.5
    assert row["mean_f1"] == 0.5
    assert row["llm_calls"] == 1


def test_build_summary():
    runs = [
        {
            "approach": "two_step",
            "expected_type": "shelf",
            "predicted_type": "shelf",
            "type_correct": True,
            "f1": 0.9,
            "price_accuracy": 1.0,
            "total_llm_ms": 2000,
            "llm_calls": 2,
        }
    ]
    summary = build_summary(runs, ["two_step"])
    assert summary["total_runs"] == 1
    assert summary["by_approach"][0]["approach"] == "two_step"
