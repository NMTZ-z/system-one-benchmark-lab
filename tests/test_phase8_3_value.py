"""A strict paired benchmark must not create missing model or native evidence."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from benchmarks.decision_value.evaluate import (
    EvaluationError, evaluate_file, evaluate_rows, validate_case, FREEZE_SCHEMA,
)
from test_phase8_3_opportunity import point


def case():
    return {
        "schema": "local-system-one/decision-value-case-v1",
        "case_id": "synthetic-001", "gate": "completion",
        "source": "synthetic", "split": "development",
        "standardized_input_sha256": "a" * 64,
        "gold": {"acceptable": ["verify"], "preferred": "verify", "oracle": "synthetic_editorial"},
        "opportunity": point(),
        "rule_only": {"decision": "verify"},
        "rules_model": {
            "guarded_decision": "verify", "raw_model_decision": None,
            "decision_source": "rule", "backend": "rule",
            "model_invoked": False, "model_completed": False, "safety_override": False,
            "model_latency_ms": None, "failure_fallback": None,
            "model_output_invalid": False,
        },
        "native": {
            "decision": None, "decision_independently_adjudicated": False,
            "task_success": None, "task_outcome_independently_verified": False,
            "provider_attempts": None,
        },
        "safety": {"retry_forbidden_by_policy": False},
    }


def test_offline_report_has_native_unknown_and_no_savings():
    result = evaluate_rows([case()])
    group = next(iter(result["groups"].values()))
    assert group["rule_only_quality"]["acceptable_accuracy"] == 1.0
    assert group["native_decision_quality"]["acceptable_accuracy"] is None
    assert group["native_verified_task_outcomes"] == 0
    assert result["actual_agent_savings"] == "NOT_MEASURED"
    assert group["model_attempted"] == 0


def test_real_model_attempt_and_override_are_distinct():
    r = case()
    r["rules_model"].update({
        "raw_model_decision": "complete", "model_invoked": True, "model_completed": True,
        "decision_source": "rule", "backend": "mlx",
        "safety_override": True, "model_latency_ms": 12.5,
    })
    result = evaluate_rows([r])
    group = next(iter(result["groups"].values()))
    assert group["model_attempted"] == group["model_completed"] == 1
    assert group["safety_overrides"] == 1
    assert group["model_latency_n"] == 1
    assert group["latency_small_sample"]


@pytest.mark.parametrize("name,change", [
    ("wrong active mode", lambda r: r["opportunity"]["authority"].update(mode="active")),
    ("missing input digest", lambda r: r.update(standardized_input_sha256="no")),
    ("fake native success", lambda r: r["native"].update(task_success=True)),
    ("model no call", lambda r: r["rules_model"].update(guarded_decision="complete")),
    ("unrecorded inference", lambda r: r["rules_model"].update(model_completed=True)),
    ("unearned full accuracy", lambda r: r["gold"].update(oracle="independent_task_and_decision")),
    ("raw body contamination", lambda r: r.update(raw_task="the secret")),
])
def test_inconsistent_evidence_rejected(name, change):
    r = case()
    change(r)
    with pytest.raises((EvaluationError, ValueError)):
        validate_case(r)


def test_model_cannot_bypass_deterministic_hard_rule():
    r = case()
    r["opportunity"] = point(rule="verify")
    r["rules_model"].update({
        "raw_model_decision": "complete", "guarded_decision": "complete",
        "model_invoked": True, "model_completed": True,
        "decision_source": "model", "backend": "mlx",
    })
    with pytest.raises(EvaluationError):
        validate_case(r)


def test_cross_split_repeated_case_id_rejected():
    rows = [case(), copy.deepcopy(case())]
    rows[1]["split"] = "adversarial"
    with pytest.raises(EvaluationError):
        evaluate_rows(rows)


def test_per_source_split_never_pooled():
    r = case()
    other = copy.deepcopy(r)
    other["case_id"] = "synthetic-002"
    other["split"] = "adversarial"
    result = evaluate_rows([r, other])
    assert len(result["groups"]) == 2


def test_freeze_checks_dataset_protocol_and_evaluator(tmp_path):
    from benchmarks.decision_value import evaluate as module
    data = tmp_path / "replay.jsonl"
    proto = tmp_path / "protocol.md"
    manifest = tmp_path / "frozen.json"
    data.write_text(json.dumps(case())+"\n")
    proto.write_text("fixed protocol")
    freeze = {
        "schema": FREEZE_SCHEMA,
        "dataset_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(proto.read_bytes()).hexdigest(),
        "evaluator_sha256": hashlib.sha256(module.Path(module.__file__).read_bytes()).hexdigest(),
        "source_commit": "062d52e753e7e00d91a536dc81e9d85b8819cb12",
        "freeze_kind": "synthetic_development",
        "model_identity": "test_fixture_model",
        "requested_backend": "rule_only", "case_count": 1,
    }
    manifest.write_text(json.dumps(freeze))
    assert evaluate_file(data, manifest, proto)["case_count"] == 1
    data.write_text(data.read_text() + "\n")
    with pytest.raises(EvaluationError, match="dataset freeze"):
        evaluate_file(data, manifest, proto)


def test_model_failure_counts_attempt_and_conservative_fail_open():
    r = case()
    r["rules_model"].update({
        "model_invoked": True, "model_completed": False,
        "decision_source": "rule", "backend": "unknown",
        "guarded_decision": "continue",
        "failure_fallback": "completion_fail_open_continue",
        "model_latency_ms": 10.0,
    })
    result = evaluate_rows([r])
    summary = next(iter(result["groups"].values()))
    assert summary["model_attempted"] == 1
    assert summary["model_completed"] == 0
    assert summary["rules_model_quality"]["acceptable_accuracy"] == 0.0


def test_malformed_model_result_still_counts_real_backend():
    r = case()
    r["rules_model"].update({
        "model_invoked": True, "model_completed": True,
        "model_output_invalid": True, "decision_source": "rule",
        "guarded_decision": "continue",
        "backend": "mlx", "model_latency_ms": 3.7,
        "failure_fallback": "completion_fail_open_continue",
    })
    summary = next(iter(evaluate_rows([r])["groups"].values()))
    assert summary["model_completed"] == 1
    assert summary["model_attempted"] == 1


def test_fake_inference_failure_without_attempt_is_rejected():
    r = case()
    r["rules_model"]["failure_fallback"] = "completion_fail_open_continue"
    r["rules_model"]["guarded_decision"] = "continue"
    with pytest.raises(EvaluationError):
        evaluate_rows([r])


def test_run_with_model_choice_override_keeps_model_source():
    r = case()
    r["rules_model"].update({
        "raw_model_decision": "complete", "model_invoked": True,
        "model_completed": True, "decision_source": "model",
        "backend": "mlx", "safety_override": True,
    })
    assert validate_case(r)["rules_model"]["decision_source"] == "model"


def test_odd_sample_p50_is_observed_value_not_zero():
    from benchmarks.decision_value.evaluate import _percentile
    assert _percentile([48.0, 52.0, 61.0], .5) == 52.0
    assert _percentile([48.0], .95) == 48.0
    assert _percentile([], .5) is None
