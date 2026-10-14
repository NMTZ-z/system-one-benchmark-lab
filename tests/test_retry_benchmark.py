"""Integrity and basic metric invariants for Phase 8C synthetic evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.retry.evaluate import FROZEN_SHA256, load_split, policy_metrics, wilson
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
