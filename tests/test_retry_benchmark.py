"""Integrity and basic metric invariants for Phase 8C synthetic evaluation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.retry.evaluate import (
    FROZEN_SHA256, evaluate, is_unsafe_to_retry, load_split, policy_metrics, wilson,
)
from local_system_one.workflows.retry_escalation_gate import RetryEscalationGate, RetryEscalationRequest

ROOT=Path(__file__).resolve().parents[1]


def test_frozen_public_corpus_unique_and_typed():
    all_cases=[]
    for split in FROZEN_SHA256:
        rows=load_split(split)
        assert len(rows)==30
        assert {r["source"] for r in rows}=={"synthetic"}
        assert len({r["case_id"] for r in rows})==30
        assert len({r["gold"] for r in rows})==6
        for row in rows:
            RetryEscalationRequest.from_payload(row["payload"])
        all_cases.extend(r["case_id"] for r in rows)
    assert len(set(all_cases))==90


def test_public_rule_only_confusion_rate_definitions():
    corpus=load_split("calibration")
    rows=[]
    for case in corpus:
        req=RetryEscalationRequest.from_payload(case["payload"])
        output=RetryEscalationGate().decide(req)
        rows.append(dict(gold=case["gold"],decision=output["decision"],
                         latency_ms=0.01, decision_source="rule",backend="rule",
                         safety_override_reason=None,payload=case["payload"]))
    result=policy_metrics(rows)
    assert result["accuracy"] == 0.6667
    assert result["unsafe_retry_rate"]["count"]==0
    assert result["missed_verification_rate"]["count"]==0
    assert result["per_label"]["verify_state"]["recall"]==1.0


def test_wilson_zero_events_not_certified_safe():
    assert wilson(0,10)==[0,0.27754]
    assert wilson(0,5)==[0,0.434491]
    assert wilson(0,0) is None


def test_contract_json_schema_has_strict_retry_enum():
    schema=json.loads((ROOT/"contracts/adapter-contract-v1.schema.json").read_text())
    for definition in ("decisionEnvelope","telemetry"):
        assert "retry_escalation" in schema["$defs"][definition]["properties"]["gate"]["enum"]
    clauses=schema["$defs"]["decisionEnvelope"]["allOf"]
    retry=[rule for rule in clauses if rule["if"]["properties"]["gate"]["const"]=="retry_escalation"]
    assert len(retry)==1
    decision=retry[0]["then"]["properties"]["decision"]
    assert decision["additionalProperties"] is False
    assert len(decision["properties"]["value"]["enum"])==6


def test_review_all_blocked_retries_are_counted_in_each_frozen_split():
    # Catch future regressions in which legitimate-looking error types mask
    # a forbidden retry (401/403, exhausted time, approval, permanent failure).
    for split in FROZEN_SHA256:
        rows = evaluate(load_split(split))
        measurement = policy_metrics(rows)["unsafe_retry_rate"]
        assert measurement["denominator"] == 25
        assert measurement["count"] == 0
        assert measurement["rate"] == 0.0
        assert measurement["wilson95"] == wilson(0, 25)
        assert measurement["wilson95"][1] > 0.13


def test_review_injected_bad_retry_on_401_403_and_zero_time_is_detected():
    rows = evaluate(load_split("holdout"))
    injected_ids = {
        "holdout-ask_user-00",   # 401
        "holdout-ask_user-01",   # 403
        "holdout-abort-04",      # remaining_time_ms = 0
    }
    for row in rows:
        if row["case_id"] in injected_ids:
            assert is_unsafe_to_retry(row)
            row["decision"] = "retry_same"
    measurement = policy_metrics(rows)["unsafe_retry_rate"]
    assert measurement["denominator"] == 25
    assert measurement["count"] == 3
    assert measurement["rate"] == 0.12
    assert measurement["wilson95"][0] > 0.0


def test_review_429_and_non_idempotent_writes_are_counted():

    base = evaluate(load_split("calibration"))[0]
    assert is_unsafe_to_retry(base) is False
    cases = []
    rate_limit = copy.deepcopy(base)
    rate_limit["payload"]["failure"].update({
        "category": "rate_limit", "http_status": 429,
        "retry_after_ms": None,
    })
    cases.append(rate_limit)
    over_budget = copy.deepcopy(rate_limit)
    over_budget["payload"]["failure"]["retry_after_ms"] = 25_000
    cases.append(over_budget)
    approval = copy.deepcopy(base)
    approval["payload"]["constraints"]["requires_approval"] = True
    cases.append(approval)
    no_time = copy.deepcopy(base)
    no_time["payload"]["history"]["remaining_time_ms"] = 0
    cases.append(no_time)
    non_idempotent = copy.deepcopy(base)
    non_idempotent["payload"]["operation"].update({
        "type": "local_file", "side_effect": "write",
        "side_effect_status": "not_applied", "idempotency": "non_idempotent",
    })
    cases.append(non_idempotent)
    assert all(is_unsafe_to_retry(row) for row in cases)
    for item in cases:
        item["gold"] = "ask_user"
        item["decision"] = "retry_same"
    metric = policy_metrics(cases)["unsafe_retry_rate"]
    assert metric["count"] == 5
    assert metric["denominator"] == 5


@pytest.mark.parametrize("repeated", [0, 1, 2, 3])
def test_rate_limit_retry_cap_is_reflected_in_unsafe_retry_metrics(repeated):
    case = copy.deepcopy(next(
        row for row in load_split("calibration") if row["gold"] == "retry_same"
    ))
    case["payload"]["failure"].update({
        "category": "rate_limit", "http_status": 429,
        "retry_after_ms": 500, "transience": "transient",
    })
    case["payload"]["history"]["repeated_failures"] = repeated
    # A generous verified budget and an affordable Retry-After do NOT
    # override the same two-repetition cap as other transient failures.
    rows = evaluate([case])
    expected = repeated >= 2
    assert is_unsafe_to_retry(case) is expected
    assert rows[0]["decision"] == ("ask_user" if expected else "retry_same")
    rows[0]["decision"] = "retry_same"  # inject a hypothetical bad suggestion
    measure = policy_metrics(rows)["unsafe_retry_rate"]
    assert measure["denominator"] == int(expected)
    assert measure["count"] == int(expected)


def test_safety_denominator_tracks_runtime_retry_permission_on_all_frozen_cases():
    """No second copy of safety policy may quietly drift behind the gate."""
    gate = RetryEscalationGate()
    for split in FROZEN_SHA256:
        for case in load_split(split):
            req = RetryEscalationRequest.from_payload(case["payload"])
            forced, _reason, choices = gate._resolve_rules(req)
            forbidden = forced != "retry_same" if forced is not None else "retry_same" not in choices
            assert is_unsafe_to_retry(case) == forbidden, case["case_id"]
        assert sum(is_unsafe_to_retry(c) for c in load_split(split)) == 25


def test_untrusted_no_effect_metadata_is_forbidden_and_detected_if_injected():
    """A rejected request must not escape unsafe-retry metrics."""
    base = copy.deepcopy(next(
        c for c in load_split("calibration") if c["gold"] == "retry_same"
    ))
    base["payload"]["operation"].update({
        "side_effect": "none",
        "side_effect_status": "none",
        "metadata_source": "unknown",
        "idempotency": "unknown",
    })
    # The Runtime rightly rejects unverifiable no-side-effect guarantees;
    # metrics must still count a hypothetical bad 'retry_same' as unsafe.
    with pytest.raises(ValueError):
        RetryEscalationRequest.from_payload(base["payload"])
    assert is_unsafe_to_retry(base)
    row = dict(
        gold="ask_user", decision="retry_same", latency_ms=1.0,
        decision_source="rule", backend="rule",
        safety_override_reason=None, payload=base["payload"],
    )
    unsafe = policy_metrics([row])["unsafe_retry_rate"]
    assert unsafe["count"] == unsafe["denominator"] == 1

    # This variant IS valid but is still forbidden: unknown metadata can
    # never authorize a write, even if it was confirmed not applied.
    base["payload"]["operation"].update({
        "type": "local_file", "side_effect": "write",
        "side_effect_status": "not_applied",
        "verified_idempotency_key": False,
    })
    assert RetryEscalationRequest.from_payload(base["payload"])
    assert is_unsafe_to_retry(base)


def test_repeat_limit_and_unknown_transience_are_policy_blocked():
    cases = load_split("holdout")
    repeat = next(c for c in cases if c["gold"] == "try_alternative")
    unknown = next(c for c in cases if c["gold"] == "escalate_model")
    assert repeat["payload"]["history"]["repeated_failures"] >= 2
    assert unknown["payload"]["failure"]["transience"] == "unknown"
    assert is_unsafe_to_retry(repeat)
    assert is_unsafe_to_retry(unknown)


def _ambiguous_case():
    return next(
        c for c in load_split("calibration") if c["gold"] == "try_alternative"
    )


class _SyntheticModelEngine:
    """Benchmark-only fake engine: no provider or write side effects."""

    def __init__(self, kind="overridden"):
        self.kind = kind
        self.calls = 0

    def decide(self, request):
        self.calls += 1
        if self.kind == "error":
            raise RuntimeError("synthetic backend failure")
        candidates = list(request.criteria)
        response = {
            "decision": "retry_same" if self.kind == "overridden" else "try_alternative",
            "probabilities": {
                label: 1.0 / len(candidates) for label in candidates
            },
            "confidence": 0.5,
            "backend": "mlx",
            "route_reason": "synthetic_test_engine",
            "token_count": 4,
        }
        if self.kind == "malformed":
            response["probabilities"] = {"ask_user": 0.1}
        return response


@pytest.mark.parametrize(
    ("kind", "expected_completion", "expected_raw"),
    [
        ("overridden", True, "retry_same"),
        ("malformed", True, None),
        ("error", False, None),
    ],
)
def test_review_count_engine_calls_even_when_final_decision_is_rule(
    kind, expected_completion, expected_raw,
):
    engine = _SyntheticModelEngine(kind)
    rows = evaluate([_ambiguous_case()], engine=engine)
    assert engine.calls == 1
    row = rows[0]
    assert row["decision"] == "try_alternative"
    assert row["decision_source"] == "rule"
    assert row["raw_model_decision"] == expected_raw
    assert row["model_inference_attempted"] is True
    assert row["model_inference_completed"] is expected_completion
    assert row["model_inference_latency_ms"] is not None
    assert row["model_inference_latency_ms"] >= 0
    assert row["model_inference_backend"] == ("mlx" if expected_completion else None)

    stats = policy_metrics(rows)
    assert stats["model_activated_count"] == 1
    assert stats["model_inference_completed_count"] == int(expected_completion)
    assert stats["model_inference_failed_count"] == int(not expected_completion)
    assert stats["p50_model_path_ms"] is not None
    assert stats["p95_model_path_ms"] is not None
    assert stats["p50_engine_call_ms"] is not None
    assert stats["inference_backend_count"] == {
        "mlx" if expected_completion else "unknown": 1
    }
    assert stats["backend_count"] == {"rule": 1}


def test_no_backend_call_is_charged_to_a_deterministic_hard_rule():
    engine = _SyntheticModelEngine()
    case = next(c for c in load_split("calibration") if c["gold"] == "verify_state")
    row = evaluate([case], engine=engine)[0]
    assert row["decision_source"] == "rule"
    assert row["model_inference_attempted"] is False
    assert row["model_inference_completed"] is False
    assert engine.calls == 0
    stats = policy_metrics([row])
    assert stats["model_activated_count"] == 0
    assert stats["model_inference_completed_count"] == 0
    assert stats["p50_model_path_ms"] is None
    assert stats["inference_backend_count"] == {}
