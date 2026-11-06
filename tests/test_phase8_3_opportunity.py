"""Adversarial Shadow-only Opportunity Contract regression tests."""
import copy

import pytest

from local_system_one.decision_opportunity import (
    CATEGORIES, OpportunityError, evaluate_opportunity,
)


def point(*, rule=None, choices=("complete", "continue", "verify")):
    return {
        "schema": "local-system-one/opportunity-v1",
        "gate": "completion",
        "observation_stage": "post_tool",
        "evidence": {
            "source": "native_observed", "status": "verified",
            "capabilities": {
                "tool_result_observation": {"status": "supported", "source": "test_fixture"}
            },
            "required_capabilities": ["tool_result_observation"],
            "verified_conditions": [],
        },
        "candidates": {
            "labels": list(choices), "bounded": True,
            "stable": True, "guard_source": "adapter_policy",
        },
        "rule": {
            "resolved": rule is not None, "decision": rule,
            "source": "adapter_policy",
        },
        "constraints": {
            "requires_generation": False, "permission_verified": False,
            "side_effect_status": "unknown",
            "retry_policy_eligible": False, "escalation_policy_eligible": False,
            "independent_verification_required": True,
        },
        "authority": {"mode": "shadow", "action_allowed": False},
    }


def test_all_four_categories_and_shadow_invariant():
    typed = evaluate_opportunity(point())
    assert typed["category"] == "typed_model_candidate"
    assert not typed["model_invoked"] and not typed["authority"]["action_allowed"]
    assert evaluate_opportunity(point(rule="continue"))["category"] == "rule_only"
    native = point()
    native["constraints"]["requires_generation"] = True
    assert evaluate_opportunity(native)["category"] == "native_agent"
    native["evidence"]["status"] = "missing"
    assert evaluate_opportunity(native)["category"] == "unsupported"
    assert CATEGORIES == {"rule_only", "typed_model_candidate", "native_agent", "unsupported"}


def test_capability_missing_and_conditional_proof():
    obj = point()
    obj["evidence"]["capabilities"] = {}
    assert evaluate_opportunity(obj)["reason"] == "required_capability_unproven"
    obj["evidence"]["capabilities"]["tool_result_observation"] = {
        "status": "conditional", "source": "test_fixture", "condition": "private_observer",
    }
    assert evaluate_opportunity(obj)["category"] == "unsupported"
    obj["evidence"]["verified_conditions"] = ["private_observer"]
    assert evaluate_opportunity(obj)["category"] == "typed_model_candidate"


@pytest.mark.parametrize("status", ["partial", "ambiguous", "missing", "unsupported"])
def test_missing_evidence_never_claims_model_readiness(status):
    obj = point(rule="continue")
    obj["evidence"]["status"] = status
    assert evaluate_opportunity(obj)["category"] == "unsupported"


@pytest.mark.parametrize("source", ["estimated", "model_reported", "platform_reported", "unknown"])
def test_untrusted_evidence_is_unsupported(source):
    obj = point()
    obj["evidence"]["source"] = source
    assert evaluate_opportunity(obj)["category"] == "unsupported"


@pytest.mark.parametrize("label,flag", [
    ("retry_same", "retry_policy_eligible"),
    ("escalate_model", "escalation_policy_eligible"),
])
def test_recovery_unsafe_candidate_is_blocked(label, flag):
    obj = point(choices=(label, "ask_user"))
    obj["gate"] = "retry_escalation"
    assert evaluate_opportunity(obj)["reason"] == "unsafe_candidate_not_prechecked"
    obj["constraints"][flag] = True
    assert evaluate_opportunity(obj)["category"] == "typed_model_candidate"


def test_model_never_grants_permission_even_for_typed_candidate():
    obj = point()
    assert obj["constraints"]["permission_verified"] is False
    assert evaluate_opportunity(obj)["category"] == "typed_model_candidate"
    assert evaluate_opportunity(obj)["authority"] == {"mode": "shadow", "action_allowed": False}


@pytest.mark.parametrize("path,bad", [
    (("authority", "mode"), "active"),
    (("authority", "action_allowed"), True),
    (("candidates", "labels"), ["complete", "complete"]),
    (("candidates", "labels"), ["task: user secret", "continue"]),
    (("evidence", "required_capabilities"), [{"bad": 1}]),
    (("constraints", "retry_policy_eligible"), "true"),
    (("rule", "decision"), "execute_shell"),
])
def test_contract_rejects_malformed_or_active_input(path, bad):
    obj = point()
    obj[path[0]][path[1]] = bad
    with pytest.raises(OpportunityError):
        evaluate_opportunity(obj)


def test_rule_must_be_policy_verified():
    obj = point(rule="continue")
    obj["rule"]["source"] = "unknown"
    assert evaluate_opportunity(obj)["category"] == "unsupported"


def test_unknown_metadata_rejected_to_avoid_raw_data_leak():
    obj = point()
    obj["raw_prompt"] = "secret"
    with pytest.raises(OpportunityError):
        evaluate_opportunity(obj)


def test_one_choice_is_not_model_opportunity():
    obj = point(choices=("verify",))
    assert evaluate_opportunity(obj)["category"] == "unsupported"


def test_forced_retry_needs_verified_policy_eligibility():
    obj = point(rule="retry_same", choices=("retry_same",))
    obj["gate"] = "retry_escalation"
    assert evaluate_opportunity(obj)["reason"] == "unsafe_deterministic_recovery"
    obj["constraints"]["retry_policy_eligible"] = True
    assert evaluate_opportunity(obj)["category"] == "rule_only"


def test_completion_and_retry_labels_cannot_cross_gates():
    obj = point()
    obj["gate"] = "retry_escalation"
    with pytest.raises(OpportunityError):
        evaluate_opportunity(obj)
