"""Integrity and basic metric invariants for Phase 8C synthetic evaluation."""

from __future__ import annotations

import json
from pathlib import Path

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
        assert measurement["denominator"] == 15
        assert measurement["count"] == 0
        assert measurement["rate"] == 0.0
        assert measurement["wilson95"] == wilson(0, 15)
        assert measurement["wilson95"][1] > 0.2


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
    assert measurement["denominator"] == 15
    assert measurement["count"] == 3
    assert measurement["rate"] == 0.2
    assert measurement["wilson95"][0] > 0.0


def test_review_429_and_non_idempotent_writes_are_counted():
    import copy

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
