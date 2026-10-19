"""Offline, privacy-constrained Evidence Contract v1 (Phase 8.2B).

No platform/LLM import, network activity, mutable Agent hooks or authority.
The validator checks structure and causal links, not the truth of attestations.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import re
from collections import Counter
from typing import Any

SCHEMA = "local-system-one/evidence-v1"
KINDS = frozenset({
    "native_event", "adapter_observation", "decision_request",
    "runtime_decision", "shadow_outcome", "agent_execution",
    "independent_verification",
})
SOURCES = frozenset({
    "native_observed", "independently_verified", "platform_reported",
    "model_reported", "estimated", "unknown",
})
EVIDENCE_STATES = frozenset({"verified", "partial", "ambiguous", "missing", "unsupported"})
CAP_STATES = frozenset({"supported", "unsupported", "conditional", "unknown"})
CAPABILITIES = frozenset({
    "tool_result_observation", "turn_identity", "session_identity",
    "model_usage_reporting", "request_attempt_observation",
    "provider_budget_enforcement", "independent_outcome_verification",
})
MODES = frozenset({"off", "shadow_healthy", "shadow_runtime_down"})
ALLOWED_EVENT_FIELDS = frozenset({
    "schema", "event_ref", "parent_ref", "run_id", "platform", "kind", "stage",
    "refs", "gate", "decision_source", "decision_model", "execution_backend",
    "raw_recommendation", "guarded_recommendation", "adapter_action_status",
    "evidence_source", "evidence_status", "policy_version", "ts_unix_ms",
    "outcome",
})
REF_KEYS = frozenset({
    "session", "turn", "native_event", "tool_call", "decision_request", "runtime_decision",
    "provider_attempt",
})
NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
OPAQUE = re.compile(r"^[a-f0-9]{32}$")
SAFE_MODEL = re.compile(r"^[a-zA-Z0-9_.:-]+(?:/[a-zA-Z0-9_.:-]+)?$")
PARENTS = {
    "native_event": frozenset(),
    "adapter_observation": frozenset({"native_event"}),
    "decision_request": frozenset({"adapter_observation"}),
    "runtime_decision": frozenset({"decision_request"}),
    "shadow_outcome": frozenset({"runtime_decision", "decision_request"}),
    "agent_execution": frozenset({"native_event"}),
    "independent_verification": frozenset({"native_event", "agent_execution", "shadow_outcome"}),
}


class EvidenceError(ValueError):
    """Invalid public evidence or contradictory causal provenance."""


def opaque_ref(secret: bytes, scope: str, raw_id: str) -> str:
    """Generate scope-keyed, non-reversible references in private space only.

    Callers MUST supply a unique secret for a bounded run and never publish it.
    This authenticates neither the collector nor the input it was given.
    """
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise EvidenceError("correlation secret must contain >=32 random bytes")
    if not isinstance(scope, str) or not NAME.fullmatch(scope):
        raise EvidenceError("invalid reference scope")
    if not isinstance(raw_id, str) or not raw_id or len(raw_id) > 2048:
        raise EvidenceError("invalid raw identity")
    digest = hmac.new(secret, (scope + "\x00" + raw_id).encode(), hashlib.sha256).hexdigest()
    return digest[:32]


def _name(value: Any, field: str) -> None:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise EvidenceError(f"{field} must be a bounded public name")


def _ref(value: Any, field: str) -> None:
    if not isinstance(value, str) or not OPAQUE.fullmatch(value):
        raise EvidenceError(f"{field} must be an anonymized 128-bit reference")


def _safe_label(value: Any, field: str) -> None:
    if value is not None:
        if not isinstance(value, str) or not SAFE_MODEL.fullmatch(value) or len(value) > 100:
            raise EvidenceError(f"{field} must be a bounded identifier, not a path or payload")


def validate_capabilities(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or set(value) - CAPABILITIES:
        raise EvidenceError("invalid capability declaration")
    result: dict[str, dict[str, str]] = {}
    for key in CAPABILITIES:
        item = value.get(key, {"status": "unknown", "source": "unknown"})
        if not isinstance(item, dict) or set(item) - {"status", "source", "condition", "version"}:
            raise EvidenceError(f"invalid capability: {key}")
        if item.get("status") not in CAP_STATES:
            raise EvidenceError(f"invalid capability status: {key}")
        _name(item.get("source"), "capability source")
        if "version" in item:
            _name(item["version"], "capability version")
        if item["status"] == "conditional":
            _name(item.get("condition"), "capability condition")
        elif "condition" in item:
            raise EvidenceError("conditions require conditional status")
        result[key] = dict(item)
    return result


def validate_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - ALLOWED_EVENT_FIELDS:
        raise EvidenceError("unknown or unsafe evidence field")
    if value.get("schema") != SCHEMA or value.get("kind") not in KINDS:
        raise EvidenceError("unsupported evidence schema or kind")
    _ref(value.get("event_ref"), "event_ref")
    if value.get("parent_ref") is not None:
        _ref(value["parent_ref"], "parent_ref")
    for field in ("run_id", "platform", "stage"):
        _name(value.get(field), field)
    if value.get("evidence_source") not in SOURCES:
        raise EvidenceError("unknown evidence_source")
    if value.get("evidence_status") not in EVIDENCE_STATES:
        raise EvidenceError("unknown evidence_status")
    refs = value.get("refs")
    if not isinstance(refs, dict) or set(refs) - REF_KEYS:
        raise EvidenceError("invalid identity refs")
    for k, v in refs.items():
        _ref(v, f"refs.{k}")
    if value.get("gate") is not None:
        _name(value["gate"], "gate")
    if value.get("decision_source") is not None:
        if value["decision_source"] not in {"rule", "model", "unknown"}:
            raise EvidenceError("invalid decision_source")
    for field in ("decision_model", "execution_backend", "raw_recommendation",
                  "guarded_recommendation", "adapter_action_status", "policy_version"):
        _safe_label(value.get(field), field)
    timestamp = value.get("ts_unix_ms")
    if timestamp is not None and (not isinstance(timestamp, int) or isinstance(timestamp, bool)
                                  or not 0 <= timestamp <= 99_999_999_999_999):
        raise EvidenceError("invalid timestamp")
    if value.get("outcome") is not None:
        if value["kind"] not in {"agent_execution", "independent_verification"}:
            raise EvidenceError("only execution/independent verification can report outcome")
        if value["outcome"] not in {"pass", "fail", "unknown"}:
            raise EvidenceError("invalid outcome")
    return value


def verify_evidence(run: dict[str, Any]) -> dict[str, Any]:
    """Accept arbitrary event order, but never infer causal identity by time.

    BAD links/duplicates/cycles are BLOCKED. Missing links are PARTIAL and cannot
    certify full integrity. Task and Agent outcomes remain separate.
    """
    required_run = {"run_id", "platform", "mode", "events", "capabilities"}
    allowed_run = required_run | {"task_case", "observed_elapsed_ms", "timing_source"}
    if not isinstance(run, dict) or not required_run.issubset(run) or set(run) - allowed_run:
        raise EvidenceError("run must have only declared public fields")
    if "task_case" in run:
        _name(run["task_case"], "task_case")
    if ("observed_elapsed_ms" in run) != ("timing_source" in run):
        raise EvidenceError("duration and timing source must be declared together")
    if "observed_elapsed_ms" in run:
        value = run["observed_elapsed_ms"]
        if (not isinstance(value, (float, int)) or isinstance(value, bool)
                or not math.isfinite(value) or not 0 <= value <= 86_400_000):
            raise EvidenceError("invalid observed elapsed milliseconds")
        if run["timing_source"] not in SOURCES:
            raise EvidenceError("invalid timing source")
    for k in ("run_id", "platform"):
        _name(run[k], k)
    if run["mode"] not in MODES:
        raise EvidenceError("invalid run mode")
    caps = validate_capabilities(run["capabilities"])
    events = run["events"]
    if not isinstance(events, list) or len(events) > 10000:
        raise EvidenceError("invalid or over-capacity event collection")
    issues: set[str] = set()
    partial_reasons: list[str] = []
    refs: dict[str, dict] = {}
    for item in events:
        event = validate_event(item)
        if event["run_id"] != run["run_id"] or event["platform"] != run["platform"]:
            issues.add("foreign_run_or_platform")
        ref = event["event_ref"]
        if ref in refs:
            issues.add("duplicate_event_ref")
        else:
            refs[ref] = event
    for event in events:
        kind, parent_ref = event["kind"], event.get("parent_ref")
        if parent_ref is None:
            if PARENTS[kind]:
                partial_reasons.append("missing_causal_parent")
            continue
        parent = refs.get(parent_ref)
        if parent is None:
            issues.add("orphan_parent")
            continue
        if parent["kind"] not in PARENTS[kind]:
            issues.add("invalid_causal_edge")
        for k in ("run_id", "platform"):
            if parent[k] != event[k]:
                issues.add("cross_run_link")
        for k in ("session", "turn", "decision_request", "tool_call"):
            x, y = event["refs"].get(k), parent["refs"].get(k)
            if x is not None and y is not None and x != y:
                issues.add("cross_" + k + "_link")
        # Identity must not materialize from nothing across a causal edge.
        if kind in {"runtime_decision", "shadow_outcome"} and (
            event["refs"].get("decision_request") is None
            or event["refs"].get("decision_request") != parent["refs"].get("decision_request")
        ):
            issues.add("decision_request_identity_conflict")
    # Cycle detection is independent of serialization / timestamp order.
    visited: set[str] = set()
    for root in refs:
        if root in visited:
            continue
        path: set[str] = set()
        node = root
        while node in refs and node not in visited:
            if node in path:
                issues.add("causal_cycle")
                break
            path.add(node)
            node = refs[node].get("parent_ref")
        visited.update(path)
    counters = Counter(e["kind"] for e in events)
    # Tool-call IDs are not globally unique: validate their declared session/
    # turn scope. Never join a result by matching clock time or tool name.
    tools: dict[str, dict[str, Any]] = {}
    for e in events:
        if e["kind"] != "native_event" or e["stage"] not in {"tool_call", "tool_result"}:
            continue
        call_ref = e["refs"].get("tool_call")
        if call_ref is None:
            partial_reasons.append("native_tool_identity_missing")
            continue
        scope = (e["refs"].get("session"), e["refs"].get("turn"))
        slot = tools.setdefault(call_ref, {"scope": scope, "stages": set()})
        if slot["scope"] != scope:
            issues.add("tool_call_reused_across_turns")
        if e["stage"] in slot["stages"]:
            issues.add("duplicate_native_tool_stage")
        slot["stages"].add(e["stage"])
    if any(slot["stages"] != {"tool_call", "tool_result"} for slot in tools.values()):
        partial_reasons.append("unpaired_native_tool")
    expected = {"native_event", "agent_execution", "independent_verification"}
    if run["mode"] != "off":
        expected.update({"adapter_observation", "decision_request", "shadow_outcome"})
    if run["mode"] == "shadow_healthy":
        expected.add("runtime_decision")
    for kind in sorted(expected):
        if counters[kind] == 0:
            partial_reasons.append("absent_" + kind)
    # A platform that declares identity support cannot omit those identities
    # from individual records and still claim complete causal coverage.
    if caps["session_identity"]["status"] == "supported":
        if any("session" not in e["refs"] for e in events):
            partial_reasons.append("declared_session_identity_missing")
    if caps["turn_identity"]["status"] == "supported":
        if any("turn" not in e["refs"] for e in events):
            partial_reasons.append("declared_turn_identity_missing")
    if any(e["evidence_source"] in {"unknown", "estimated", "model_reported"}
           for e in events):
        partial_reasons.append("untrusted_or_unknown_provenance")
    # Missing signals are coverage gaps even if the adapter correctly says unsupported.
    coverage_gaps = sorted(k for k, item in caps.items() if item["status"] != "supported")
    if coverage_gaps:
        partial_reasons.append("capability_coverage_gap")
    if any(e["evidence_status"] != "verified" for e in events):
        partial_reasons.append("nonverified_event")
    # Do not equate a platform/model assertion to independent verification.
    independent = [e for e in events if e["kind"] == "independent_verification"
                   and e["evidence_status"] == "verified"
                   and e["evidence_source"] == "independently_verified"]
    agent = [e for e in events if e["kind"] == "agent_execution"
             and e["evidence_status"] == "verified"
             and e["evidence_source"] in {"native_observed", "independently_verified"}]
    def verdict(rows: list[dict]) -> str:
        vals = {v.get("outcome") for v in rows}
        if len(vals) > 1:
            issues.add("contradictory_outcomes")
            return "UNKNOWN"
        return {"pass": "PASS", "fail": "FAIL"}.get(next(iter(vals), None), "UNKNOWN")
    task = verdict(independent)
    execution = verdict(agent)
    if not independent:
        partial_reasons.append("no_independent_task_attestation")
    if not agent:
        partial_reasons.append("no_native_execution_attestation")
    # A matching HMAC ref is only a correlation handle; it is not a proof of authenticity.
    integrity = "BLOCKED" if issues else "PARTIAL" if partial_reasons else "PASS"
    return {
        "run_id": run["run_id"], "platform": run["platform"], "mode": run["mode"],
        "task_case": run.get("task_case"),
        "observed_elapsed_ms": run.get("observed_elapsed_ms"),
        "timing_source": run.get("timing_source", "unknown"),
        "native_tool_calls": sum(e["kind"] == "native_event" and e["stage"] == "tool_call" for e in events),
        "native_tool_results": sum(e["kind"] == "native_event" and e["stage"] == "tool_result" for e in events),
        "runtime_unavailable_events": sum(e["kind"] == "shadow_outcome"
                                          and e["stage"] == "runtime_unavailable" for e in events),
        "task_outcome": task, "agent_execution_outcome": execution,
        "evidence_integrity": integrity, "issues": sorted(issues),
        "coverage_gaps": coverage_gaps, "partial_reasons": sorted(set(partial_reasons)),
        "event_counts": dict(sorted(counters.items())),
    }
