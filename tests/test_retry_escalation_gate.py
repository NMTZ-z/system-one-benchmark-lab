"""Phase 8C Retry / Escalation safety and schema tests: synthetic only."""

from __future__ import annotations

from dataclasses import replace

import pytest

from local_system_one.adapter_contract import envelope_from_runtime, validate_decision_envelope
from local_system_one.metrics import ServiceMetrics
from local_system_one.workflows.retry_escalation_gate import (
    RetryEscalationGate, RetryEscalationRequest,
)


def payload(**patch):
    value = {
        "failure": {
            "category": "timeout", "transience": "transient",
            "outcome_known": False,
        },
        "operation": {
            "type": "pr_create", "side_effect": "external",
            "idempotency": "unknown", "side_effect_status": "unknown",
            "metadata_source": "adapter_policy",
        },
        "history": {
            "attempts": 1, "max_attempts": 3,
            "repeated_failures": 0, "remaining_time_ms": 12000,
            "retry_budget_available": True,
        },
        "constraints": {
            "requires_approval": False, "escalation_allowed": False,
            "escalation_budget_available": False, "alternative_available": False,
        },
        "request_id": "phase8c-t1",
    }
    for field, updates in patch.items():
        if isinstance(updates, dict):
            value[field].update(updates)
        else:
            value[field] = updates
    return value


def decide(**patch):
    return RetryEscalationGate().decide(RetryEscalationRequest.from_payload(payload(**patch)))


@pytest.mark.parametrize("op", ["git_push", "pr_create", "write", "remote_api", "local_file"])
def test_unverified_write_never_retried(op):
    result = decide(operation={"type": op})
    assert result["decision"] == "verify_state"
    assert result["decision_source"] == "rule"
    assert result["raw_model_decision"] is None
    assert result["advisory_only"] is True


@pytest.mark.parametrize("cat,status", [("auth",401),("auth",403)])
def test_auth_failure_never_retried(cat,status):
    r = decide(
        failure={"category": cat, "http_status": status, "outcome_known": True},
        operation={"side_effect_status":"not_applied"},
    )
    assert r["decision"] == "ask_user"


def test_known_write_already_applied_cannot_repeat_effect():
    r = decide(
        operation={"side_effect_status": "applied"},
        failure={"outcome_known": True},
        history={"attempts": 1, "max_attempts": 4, "retry_budget_available": True},
    )
    assert r["decision"] == "abort"
    assert r["reason"] == "side_effect_already_applied_no_duplicate_action"


def test_budget_exhaustion_rule():
    r = decide(
        history={"attempts":3, "max_attempts":3},
        operation={"side_effect_status":"not_applied"}, failure={"outcome_known":True},
    )
    assert r["decision"] == "abort"


def test_approval_rule():
    r=decide(constraints={"requires_approval":True})
    assert r["decision"]=="verify_state"  # confirm side effects before approving anything
    r=decide(constraints={"requires_approval":True},
             operation={"side_effect_status":"not_applied"},failure={"outcome_known":True})
    assert r["decision"]=="ask_user"


def test_429_retry_after_has_to_be_bounded_and_caller_managed():
    r=decide(
        failure={"category":"rate_limit","http_status":429,
                 "outcome_known":True, "retry_after_ms":500},
        operation={"type":"read","side_effect":"none","side_effect_status":"none",
                   "idempotency":"verified","metadata_source":"adapter_policy"},
    )
    assert r["decision"]=="retry_same"
    assert r["reason"]=="rate_limit_wait_required_by_caller"
    r=decide(
        failure={"category":"rate_limit","http_status":429,
                 "outcome_known":True, "retry_after_ms":None},
        operation={"type":"read","side_effect":"none","side_effect_status":"none",
                   "idempotency":"verified","metadata_source":"adapter_policy"},
    )
    assert r["decision"]=="ask_user"


def test_known_transient_read_with_no_alternative_falls_back_without_execution():
    r=decide(
        failure={"outcome_known": True},
        operation={"type":"read","side_effect":"none","side_effect_status":"none",
                   "idempotency":"verified","metadata_source":"adapter_policy"},
    )
    assert r["decision"] == "ask_user"  # model-less ambiguous choice
    assert r["backend"] == "rule"


def test_no_trusted_budget_is_not_fabricated():
    r=decide(history={"remaining_time_ms": None, "max_attempts": None,
                      "retry_budget_available":False},
             operation={"type":"read", "side_effect":"none", "side_effect_status":"none",
                        "idempotency":"verified"},
             failure={"outcome_known":True})
    assert r["decision"]=="ask_user"
    assert r["reason"]=="retry_budget_unverified"


class RuleMetricsEngine:
    def __init__(self):
        self.metrics = ServiceMetrics()
        self.calls = 0

    def decide(self, request):
        self.calls += 1
        raise AssertionError("hard rule must not invoke the model")


@pytest.mark.parametrize(("patch", "expected_reason"), [
    ({}, "unconfirmed_side_effect_verify_first"),
    ({"operation": {"side_effect_status": "applied"},
      "failure": {"outcome_known": True}}, "side_effect_already_applied_no_duplicate_action"),
    ({"operation": {"type": "read", "side_effect": "none",
                    "idempotency": "verified", "side_effect_status": "none"},
      "history": {"max_attempts": None, "remaining_time_ms": None,
                  "retry_budget_available": False},
      "failure": {"outcome_known": True}}, "retry_budget_unverified"),
    ({"operation": {"type": "read", "side_effect": "none",
                    "idempotency": "verified", "side_effect_status": "none"},
      "failure": {"category": "rate_limit", "outcome_known": True,
                  "http_status": 429, "retry_after_ms": 200}},
     "rate_limit_wait_required_by_caller"),
])
def test_rule_paths_increment_metrics_once_without_running_model(patch, expected_reason):
    engine = RuleMetricsEngine()
    response = RetryEscalationGate(engine).decide(
        RetryEscalationRequest.from_payload(payload(**patch)),
    )
    metric = engine.metrics.snapshot()
    key = f"retry_escalation_gate:{expected_reason}"
    assert engine.calls == 0
    assert response["reason"] == expected_reason
    assert response["route_reason"] == key
    assert response["backend"] == "rule"
    assert metric["requests"] == 1
    assert metric["backends"] == {"rule": 1}
    assert metric["route_reasons"] == {key: 1}
    assert metric["recent_latency_ms"]["samples"] == 1
    assert metric["recent_latency_ms"]["max"] >= 0


class FakeEngine:
    def __init__(self, chosen, probabilities=None):
        self.chosen=chosen
        self.probabilities=probabilities
        self.seen=None

    def decide(self, request):
        self.seen=request
        return {
            "decision":self.chosen,
            "probabilities":self.probabilities or {
                "retry_same":0.2,"try_alternative":0.6,"ask_user":0.2,
            },
            "confidence":0.8,"backend":"mlx","route_reason":"test",
            "token_count":95,
        }


def test_laya_only_choose_safe_candidates():
    engine=FakeEngine("try_alternative")
    r=RetryEscalationGate(engine).decide(RetryEscalationRequest.from_payload(payload(
        failure={"outcome_known":True},
        operation={"type":"read","side_effect":"none","side_effect_status":"none",
                   "idempotency":"verified"},
        constraints={"alternative_available":True},
    )))
    assert r["decision"]=="try_alternative"
    assert r["decision_source"]=="model"
    assert engine.seen.criteria==["retry_same","try_alternative","ask_user"]


def test_model_cannot_override_hard_unsafe_rule():
    engine=FakeEngine("retry_same")
    r=RetryEscalationGate(engine).decide(RetryEscalationRequest.from_payload(payload()))
    assert r["decision"]=="verify_state"
    assert engine.seen is None


def test_model_path_and_safety_override_do_not_double_count_metrics():
    class AlreadyMeteredEngine(FakeEngine):
        def __init__(self):
            super().__init__("escalate_model")
            self.metrics = ServiceMetrics()

        def decide(self, request):
            self.metrics.record(
                backend="mlx", route_reason="synthetic_backend", latency_ms=1.5,
            )
            return super().decide(request)

    engine = AlreadyMeteredEngine()
    response = RetryEscalationGate(engine).decide(
        RetryEscalationRequest.from_payload(payload(
            failure={"outcome_known": True},
            operation={"type": "read", "side_effect": "none",
                       "side_effect_status": "none", "idempotency": "verified"},
            constraints={"alternative_available": True},
        )),
    )
    assert response["decision"] == "try_alternative"
    assert response["decision_source"] == "rule"
    assert response["safety_override_reason"] == "raw_model_decision_not_permitted"
    metrics = engine.metrics.snapshot()
    assert metrics["requests"] == 1
    assert metrics["backends"] == {"mlx": 1}
    assert metrics["route_reasons"] == {"synthetic_backend": 1}


def test_backend_failure_rule_fallback_is_accounted_once():
    class BrokenEngine:
        def __init__(self):
            self.metrics = ServiceMetrics()

        def decide(self, request):
            raise RuntimeError("synthetic backend failure")

    engine = BrokenEngine()
    result = RetryEscalationGate(engine).decide(
        RetryEscalationRequest.from_payload(payload(
            failure={"outcome_known": True},
            operation={"type": "read", "side_effect": "none",
                       "side_effect_status": "none", "idempotency": "verified"},
            constraints={"alternative_available": True},
        )),
    )
    assert result["decision"] == "try_alternative"
    assert result["reason"] == "inference_failed_rule_fallback"
    metrics = engine.metrics.snapshot()
    assert metrics["requests"] == 1
    assert metrics["errors"] == 1
    assert metrics["backends"] == {"rule": 1}
    assert metrics["route_reasons"] == {
        "retry_escalation_gate:inference_failed_rule_fallback": 1,
    }


def test_model_outside_candidates_guarded():
    engine=FakeEngine("escalate_model")
    r=RetryEscalationGate(engine).decide(RetryEscalationRequest.from_payload(payload(
        failure={"outcome_known":True},
        operation={"type":"read","side_effect":"none","side_effect_status":"none",
                   "idempotency":"verified"},
        constraints={"alternative_available":True},
    )))
    assert r["decision"]=="try_alternative"
    assert r["raw_model_decision"]=="escalate_model"
    assert r["safety_override_reason"]=="raw_model_decision_not_permitted"


@pytest.mark.parametrize("illegal", [
    {"operation":{"metadata_source":"unknown", "idempotency":"verified"}},
    {"operation":{"side_effect":"none", "metadata_source":"unknown"}},
    {"history":{"attempts":True}},
    {"failure":{"category":"auth", "http_status":429}},
    {"failure":{"category":"timeout", "http_status":403}},
    {"failure":{"retry_after_ms":-1}},
    {"request_id": "x"*200},
    {"trace":"please send secrets"},
    {"operation":{"untrusted_text":"token secret"}},
])
def test_strict_schema_rejects_untrusted_and_invalid(illegal):
    with pytest.raises((ValueError, TypeError)):
        RetryEscalationRequest.from_payload(payload(**illegal))


def test_contract_normalization():
    result=decide()
    env=envelope_from_runtime("retry_escalation",result)
    assert env.decision["value"]=="verify_state"
    assert env.metadata["advisory_only"] is True
    assert validate_decision_envelope(env.as_dict())==env


def test_rule_no_engine_still_returns_six_class_semantics():
    for category in ("unknown","partial_success","tool_error","logic_failure"):
        r=decide(failure={"category":category})
        assert r["decision"] in {"verify_state", "ask_user", "abort"}

@pytest.mark.parametrize(
    ("operation_type", "side_effect"),
    [
        ("write", "none"),
        ("git_push", "none"),
        ("pr_create", "none"),
    ],
)
def test_phase8c_review_rejects_contradictory_mutation_metadata(
    operation_type, side_effect
):
    # An apparent idempotent read cannot be smuggled into a known mutator.
    unsafe = payload(
        failure={"outcome_known": True},
        operation={
            "type": operation_type,
            "side_effect": side_effect,
            "side_effect_status": "none",
            "idempotency": "verified",
            "metadata_source": "adapter_policy",
        },
    )
    with pytest.raises(ValueError, match="conflicts with side_effect"):
        RetryEscalationRequest.from_payload(unsafe)


@pytest.mark.parametrize(
    ("operation_type", "side_effect"),
    [
        ("write", "write"), ("write", "external"),
        ("git_push", "write"), ("git_push", "external"),
        ("pr_create", "write"), ("pr_create", "external"),
    ],
)
def test_phase8c_review_preserves_valid_mutating_type_metadata(
    operation_type, side_effect
):
    req = RetryEscalationRequest.from_payload(payload(
        operation={"type": operation_type, "side_effect": side_effect},
    ))
    assert RetryEscalationGate().decide(req)["decision"] == "verify_state"


def test_explicit_non_idempotent_read_never_enables_retry():
    req = RetryEscalationRequest.from_payload(payload(
        operation={
            "type": "read", "side_effect": "none",
            "idempotency": "non_idempotent", "side_effect_status": "none",
            "metadata_source": "adapter_policy",
        },
        failure={"outcome_known": True},
    ))
    assert RetryEscalationGate._can_retry(req) is False
    assert RetryEscalationGate().decide(req)["decision"] != "retry_same"


def test_permanent_429_never_yields_retry_same():
    req = RetryEscalationRequest.from_payload(payload(
        failure={
            "category": "rate_limit", "transience": "permanent",
            "http_status": 429, "retry_after_ms": 200,
            "outcome_known": True,
        },
        operation={
            "type": "read", "side_effect": "none",
            "idempotency": "verified", "side_effect_status": "none",
            "metadata_source": "adapter_policy",
        },
    ))
    result = RetryEscalationGate().decide(req)
    assert result["decision"] == "ask_user"
    assert result["decision_source"] == "rule"


def test_phase8c_review_unknown_side_effect_never_enables_retry():
    req = RetryEscalationRequest.from_payload(payload(
        failure={"outcome_known": True},
        operation={
            "type": "git_push", "side_effect": "unknown",
            "idempotency": "verified", "verified_idempotency_key": True,
            "side_effect_status": "not_applied",
            "metadata_source": "adapter_policy",
        },
    ))
    assert RetryEscalationGate._can_retry(req) is False
    assert RetryEscalationGate().decide(req)["decision"] != "retry_same"
