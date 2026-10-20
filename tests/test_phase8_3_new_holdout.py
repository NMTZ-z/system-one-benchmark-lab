"""Pre-model audit of 80 newly authored synthetic/fault-injection scenarios.

No model load or Provider requests; fake engine observes only sanitized inputs.
"""
from __future__ import annotations

import copy
import json
from collections import Counter

import pytest

from benchmarks.decision_value.evaluate import evaluate_rows
from benchmarks.decision_value.holdout_v1.build_frozen import build
from benchmarks.decision_value.holdout_v1.replay import (
    HoldoutError, check_freeze, read_cases, replay,
)
from local_system_one.workflows.retry_escalation_gate import (
    RetryEscalationGate, RetryEscalationRequest,
)


class DummyMetrics:
    def record(self, **kwargs):
        return None


class DummyHealth:
    def snapshot(self):
        return self

    def as_dict(self):
        return {"healthy": False}


class StubEngine:
    def __init__(self):
        self.metrics = DummyMetrics()
        self.health = DummyHealth()
        self.requests = []

    def decide(self, request):
        self.requests.append(request)
        criteria = request.criteria
        options = list(criteria)
        selected = options[0]
        probabilities = {key: (1.0 if key == selected else 0.0) for key in options}
        return {
            "decision": selected, "probabilities": probabilities,
            "confidence": 1.0, "backend": "mlx",
            "route_reason": "test_only", "token_count": 12, "latency_ms": 1.0,
        }


def test_new_frozen_corpus_has_exact_cardinality_and_no_prior_input_overlap():
    cases = build()
    assert len(cases) == 80
    assert {r["id"] for r in cases} == {f"new-c{i:03d}" for i in range(1, 41)} | {
        f"new-r{i:03d}" for i in range(1, 41)}
    assert len({r["family"] for r in cases}) == 80
    assert Counter(r["source"] for r in cases) == {"synthetic": 40, "fault_injection": 40}
    assert Counter(r["gate"] for r in cases) == {"completion": 40, "retry_escalation": 40}
    assert cases == read_cases()


def test_predeclared_multi_label_and_prechecked_safe_retry_candidates():
    cases = read_cases()
    multi = [c for c in cases if len(c["gold"]["acceptable"]) > 1]
    assert len(multi) >= 9
    for c in cases[40:]:
        req = RetryEscalationRequest.from_payload(c["input"])
        _, _, choices = RetryEscalationGate()._resolve_rules(req)
        assert set(c["gold"]["acceptable"]).issubset(set(choices)), c["id"]


def test_rule_only_pipeline_is_not_a_fabricated_model_run():
    rows = replay(read_cases(), None)
    assert len(rows) == 80
    assert all(not r["rules_model"]["model_invoked"] for r in rows)
    summary = evaluate_rows(rows)
    assert set(summary["groups"]) == {
        "completion/synthetic/frozen_holdout",
        "retry_escalation/fault_injection/frozen_holdout",
    }
    assert all(v["native_decision_quality"]["observed"] == 0 for v in summary["groups"].values())
    assert all(v["native_verified_task_outcomes"] == 0 for v in summary["groups"].values())


def test_stub_backend_observes_no_hidden_oracle_or_labels():
    cases = read_cases()
    stub = StubEngine()
    rows = replay(cases, stub)
    assert len(rows) == 80
    assert len(stub.requests) == 29
    assert sum(r["rules_model"]["model_invoked"] for r in rows) == len(stub.requests)
    for request in stub.requests:
        state = json.dumps(request.state, sort_keys=True)
        assert '"gold"' not in state
        assert '"acceptable"' not in state
        assert '"preferred"' not in state
        assert '"oracle"' not in state
        assert '"family"' not in state
        for c in cases:
            assert c["gold"]["basis"] not in state
    assert all(not r["opportunity"]["authority"]["action_allowed"] for r in rows)


def test_non_ancestor_or_fake_freeze_commit_is_rejected_before_model():
    with pytest.raises(HoldoutError):
        check_freeze("bad")
    with pytest.raises(HoldoutError):
        check_freeze("0" * 40)


def test_no_relabeling_gold_after_capture():
    cases = read_cases()
    fake = StubEngine()
    before = [copy.deepcopy(r["gold"]) for r in cases]
    replay(cases, fake)
    assert [r["gold"] for r in cases] == before


def test_simulated_oracle_metadata_is_not_a_native_task_verification():
    rows = replay(read_cases(), None)
    assert set(r["gold"]["oracle"] for r in rows) == {"synthetic_editorial", "fault_oracle"}
    assert all(r["native"]["task_success"] is None for r in rows)
    assert all(r["native"]["provider_attempts"] is None for r in rows)
