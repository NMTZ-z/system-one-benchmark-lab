"""Tests for typed-decisions scoring."""

import pytest

from benchmarks.quality.metrics import score_records


def test_binary_perfect_prediction():
    records = [
        {
            "workflow": "x",
            "question_name": "q",
            "question_type": "noul",
            "question": {"type": "noul"},
            "gold": {
                "type": "noul",
                "label": "true",
                "noul": 0.8,
                "probabilities": {"false": 0.2, "true": 0.8},
            },
            "answer": {"type": "noul", "noul": 0.8},
            "status": "ok",
        }
    ]
    result = score_records(records)
    assert result["accuracy"] == 1.0
    assert result["soft_accuracy"] == pytest.approx(0.68)
    assert result["brier_vs_soft"] == pytest.approx(0.0, abs=1e-15)
    assert result["coverage"] == 1.0


def test_failure_reduces_coverage():
    records = [
        {
            "workflow": "x",
            "question_name": "q",
            "question_type": "noul",
            "question": {"type": "noul"},
            "gold": {
                "type": "noul",
                "label": "true",
                "noul": 1.0,
                "probabilities": {"false": 0.0, "true": 1.0},
            },
            "answer": None,
            "status": "capacity_error",
        }
    ]
    result = score_records(records)
    assert result["coverage"] == 0.0
    assert result["failures"] == {"capacity_error": 1}
