"""Phase 8.3 advisory Decision Opportunity Contract v1.

Offline/Shadow analysis only. This module cannot call a model, execute a tool,
change adapter authority or alter existing Gate thresholds.
"""
from __future__ import annotations

from typing import Any

from .evidence_integrity import (
    CAPABILITIES, EVIDENCE_STATES, NAME, SOURCES, validate_capabilities,
)

SCHEMA = "local-system-one/opportunity-v1"
CATEGORIES = frozenset({"rule_only", "typed_model_candidate", "native_agent", "unsupported"})
STAGES = frozenset({"pre_tool", "post_tool", "turn_end", "on_error"})
SIDE_EFFECT_STATES = frozenset({"none", "not_applied", "applied", "partial", "unknown"})
ALLOWED_LABELS = frozenset({
    "complete", "continue", "verify",
    "retry_same", "try_alternative", "escalate_model",
    "verify_state", "ask_user", "abort",
    "search", "skip_search", "notify", "skip_notify",
    "local", "standard", "strong",
})
MAX_CHOICES = 12
GATE_LABELS = {
    "completion": frozenset({"complete", "continue", "verify"}),
    "retry_escalation": frozenset({
        "retry_same", "try_alternative", "escalate_model",
        "verify_state", "ask_user", "abort",
    }),
}


class OpportunityError(ValueError):
    """An invalid, non-auditable or potentially unsafe analysis input."""


def _object(value: Any, fields: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) - fields:
        raise OpportunityError(f"{name} must be an object with only {sorted(fields)}")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise OpportunityError(f"{name} must be boolean")
    return value


def _labels(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_CHOICES:
        raise OpportunityError("candidate labels must be a bounded list")
    if any(not isinstance(v, str) or v not in ALLOWED_LABELS for v in value):
        raise OpportunityError("candidate label must be a registered decision, not raw content")
    if len(set(value)) != len(value):
        raise OpportunityError("duplicate candidate label")
    return list(value)


def evaluate_opportunity(value: Any) -> dict[str, Any]:
    """Classify an observed decision point; never grant execution permission.

    Claims of adapter policy and verified capabilities require independent
    provenance checking by the isolated collector. Schema validation cannot
    authenticate a fabricated observer, platform event or permission claim.
    """
    top = _object(value, {
        "schema", "gate", "observation_stage", "evidence", "candidates",
        "rule", "constraints", "authority",
    }, "opportunity")
    if top.get("schema") != SCHEMA:
        raise OpportunityError("unsupported opportunity schema")
    gate = top.get("gate")
    if not isinstance(gate, str) or not NAME.fullmatch(gate):
        raise OpportunityError("invalid gate name")
    stage = top.get("observation_stage")
    if stage not in STAGES:
        raise OpportunityError("unknown observation stage")

    evidence = _object(top.get("evidence"), {
        "source", "status", "capabilities", "required_capabilities", "verified_conditions",
    }, "evidence")
    if evidence.get("source") not in SOURCES or evidence.get("status") not in EVIDENCE_STATES:
        raise OpportunityError("invalid evidence provenance/status")
    try:
        capabilities = validate_capabilities(evidence.get("capabilities"))
    except ValueError as exc:
        raise OpportunityError("invalid 8.2B capability declaration") from exc
    required = evidence.get("required_capabilities")
    if not isinstance(required, list) or len(required) > len(CAPABILITIES):
        raise OpportunityError("invalid required capabilities")
    if (any(not isinstance(x, str) or x not in CAPABILITIES for x in required)
            or len(set(required)) != len(required)):
        raise OpportunityError("unsupported/duplicate required capability")
    conditions = evidence.get("verified_conditions")
    if not isinstance(conditions, list) or len(conditions) > 16:
        raise OpportunityError("invalid verified conditions")
    if any(not isinstance(x, str) or not NAME.fullmatch(x) for x in conditions):
        raise OpportunityError("invalid condition alias")
    if len(set(conditions)) != len(conditions):
        raise OpportunityError("duplicate verified condition")

    cand = _object(top.get("candidates"), {
        "labels", "bounded", "stable", "guard_source",
    }, "candidates")
    labels = _labels(cand.get("labels"))
    bounded = _boolean(cand.get("bounded"), "candidates.bounded")
    stable = _boolean(cand.get("stable"), "candidates.stable")
    if cand.get("guard_source") not in {"adapter_policy", "unknown"}:
        raise OpportunityError("invalid candidate guard source")

    if gate in GATE_LABELS and not set(labels).issubset(GATE_LABELS[gate]):
        raise OpportunityError("candidate label does not belong to this Gate")

    rule = _object(top.get("rule"), {"resolved", "decision", "source"}, "rule")
    resolved = _boolean(rule.get("resolved"), "rule.resolved")
    rule_decision = rule.get("decision")
    if resolved != (rule_decision is not None):
        raise OpportunityError("resolved rule requires exactly one decision")
    if rule_decision is not None and (
        rule_decision not in ALLOWED_LABELS or
        (gate in GATE_LABELS and rule_decision not in GATE_LABELS[gate])
    ):
        raise OpportunityError("invalid deterministic rule label for Gate")
    if rule.get("source") not in {"adapter_policy", "unknown"}:
        raise OpportunityError("invalid rule provenance")

    constraints = _object(top.get("constraints"), {
        "requires_generation", "permission_verified", "side_effect_status",
        "retry_policy_eligible", "escalation_policy_eligible",
        "independent_verification_required",
    }, "constraints")
    for name in (
        "requires_generation", "permission_verified", "retry_policy_eligible",
        "escalation_policy_eligible", "independent_verification_required",
    ):
        _boolean(constraints.get(name), f"constraints.{name}")
    if constraints.get("side_effect_status") not in SIDE_EFFECT_STATES:
        raise OpportunityError("invalid side-effect status")

    authority = _object(top.get("authority"), {"mode", "action_allowed"}, "authority")
    if authority.get("mode") != "shadow" or authority.get("action_allowed") is not False:
        raise OpportunityError("opportunity analysis is Shadow-only, never Active")

    gaps: list[str] = []
    for name in required:
        cap = capabilities[name]
        if cap["status"] == "supported":
            continue
        if cap["status"] == "conditional" and cap["condition"] in conditions:
            continue
        gaps.append(name)

    if evidence["source"] not in {"native_observed", "independently_verified"} or evidence["status"] != "verified":
        category, reason = "unsupported", "evidence_not_verified"
    elif gaps:
        category, reason = "unsupported", "required_capability_unproven"
    elif resolved:
        forbidden_recovery = (
            (rule_decision == "retry_same" and not constraints["retry_policy_eligible"])
            or (rule_decision == "escalate_model" and not constraints["escalation_policy_eligible"])
        )
        if forbidden_recovery:
            category, reason = "unsupported", "unsafe_deterministic_recovery"
        elif rule["source"] == "adapter_policy":
            category, reason = "rule_only", "trusted_deterministic_rule"
        else:
            category, reason = "unsupported", "rule_policy_unverified"
    elif constraints["requires_generation"]:
        category, reason = "native_agent", "requires_generation_or_planning"
    elif not bounded or not stable or len(labels) < 2:
        category, reason = "unsupported", "candidates_not_bounded_and_stable"
    elif cand["guard_source"] != "adapter_policy":
        category, reason = "unsupported", "candidate_policy_unverified"
    elif ("retry_same" in labels and not constraints["retry_policy_eligible"]) or (
        "escalate_model" in labels and not constraints["escalation_policy_eligible"]
    ):
        category, reason = "unsupported", "unsafe_candidate_not_prechecked"
    else:
        category, reason = "typed_model_candidate", "bounded_safe_candidate_set"

    return {
        "schema": SCHEMA,
        "gate": gate,
        "observation_stage": stage,
        "category": category,
        "reason": reason,
        "candidate_labels": labels,
        "candidate_count": len(labels),
        "required_capability_gaps": gaps,
        "rule_decision": rule_decision,
        "model_invoked": False,
        "authority": {"mode": "shadow", "action_allowed": False},
    }
