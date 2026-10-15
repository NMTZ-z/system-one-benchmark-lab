"""Platform-neutral adapter contract helpers.

The Local System One HTTP workflows intentionally keep their existing wire shape.
This module defines the stable semantic layer that adapters can normalize those
workflow responses into without importing platform-specific concepts such as
tool names, providers, or reasoning-effort knobs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

ADAPTER_CONTRACT_VERSION = "1.0"

GateName = Literal["search", "model_tier", "notification", "completion", "retry_escalation"]
AdapterMode = Literal["off", "shadow", "canary"]
DecisionSource = Literal["rule", "model"]
ActionStatus = Literal["observed", "applied", "skipped", "failed_open", "unsupported"]

_GATES = {"search", "model_tier", "notification", "completion", "retry_escalation"}
_ACTION_STATUSES = {"observed", "applied", "skipped", "failed_open", "unsupported"}


class AdapterContractError(ValueError):
    """Raised when an adapter-contract record is malformed or unsupported."""


def _record(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdapterContractError(f"{field} must be an object")
    return value


def _string(value: Any, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise AdapterContractError(f"{field} must be a non-empty string")
    return value


def _number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AdapterContractError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise AdapterContractError(f"{field} must be a finite number")
    return result


def _probability(value: Any, field: str) -> float:
    result = _number(value, field)
    if not 0.0 <= result <= 1.0:
        raise AdapterContractError(f"{field} must be in [0, 1]")
    return result


@dataclass(frozen=True)
class ActionOutcome:
    """What an adapter did after receiving a valid Local System One decision."""

    status: ActionStatus
    reason: str

    def __post_init__(self) -> None:
        if self.status not in _ACTION_STATUSES:
            raise AdapterContractError(f"unsupported action status: {self.status}")
        if not isinstance(self.reason, str) or not self.reason:
            raise AdapterContractError("action outcome reason must be non-empty")

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "reason": self.reason}


@dataclass(frozen=True)
class DecisionEnvelope:
    """Normalized platform-independent decision exposed to an adapter."""

    gate: GateName
    decision: dict[str, Any]
    decision_source: DecisionSource
    reason: str
    backend: str
    latency_ms: float
    request_id: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] | None = None
    adapter_contract_version: str = ADAPTER_CONTRACT_VERSION

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "adapter_contract_version": self.adapter_contract_version,
            "request_id": self.request_id,
            "gate": self.gate,
            "decision": dict(self.decision),
            "decision_source": self.decision_source,
            "reason": self.reason,
            "backend": self.backend,
            "latency_ms": self.latency_ms,
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


def validate_decision_envelope(value: Any) -> DecisionEnvelope:
    """Validate and normalize a v1 Decision Envelope.

    Top-level contract fields are strict. ``metadata`` is intentionally the one
    open extension point: unknown metadata keys are allowed so adapters can add
    non-sensitive observations without changing the decision semantics.
    """

    record = _record(value, "decision envelope")
    allowed = {
        "adapter_contract_version",
        "request_id",
        "gate",
        "decision",
        "decision_source",
        "reason",
        "backend",
        "latency_ms",
        "confidence",
        "metadata",
    }
    unknown = set(record) - allowed
    if unknown:
        raise AdapterContractError(f"unknown decision envelope field(s): {sorted(unknown)!r}")
    # request_id is required-but-nullable in the published JSON Schema.
    # A missing key is not an explicit null.
    if "request_id" not in record:
        raise AdapterContractError("missing decision envelope field: request_id")

    version = _string(record.get("adapter_contract_version"), "adapter_contract_version")
    if version != ADAPTER_CONTRACT_VERSION:
        raise AdapterContractError(f"unsupported adapter contract version: {version}")

    gate = _string(record.get("gate"), "gate")
    if gate not in _GATES:
        raise AdapterContractError(f"unknown gate: {gate}")

    decision_source = _string(record.get("decision_source"), "decision_source")
    if decision_source not in {"rule", "model"}:
        raise AdapterContractError(f"unsupported decision source: {decision_source}")

    decision = _record(record.get("decision"), "decision")
    normalized_decision = _validate_gate_decision(gate, decision)
    latency_ms = _number(record.get("latency_ms"), "latency_ms")
    if latency_ms < 0:
        raise AdapterContractError("latency_ms cannot be negative")

    # These fields are optional, but NOT nullable under the published schema.
    confidence = (
        _probability(record["confidence"], "confidence")
        if "confidence" in record else None
    )
    metadata = (
        dict(_record(record["metadata"], "metadata"))
        if "metadata" in record else None
    )

    return DecisionEnvelope(
        adapter_contract_version=version,
        request_id=_string(record.get("request_id"), "request_id", nullable=True),
        gate=gate,  # type: ignore[arg-type]
        decision=normalized_decision,
        decision_source=decision_source,  # type: ignore[arg-type]
        reason=_string(record.get("reason"), "reason") or "",
        backend=_string(record.get("backend"), "backend") or "",
        latency_ms=latency_ms,
        confidence=confidence,
        metadata=metadata,
    )


def _validate_gate_decision(gate: str, decision: dict[str, Any]) -> dict[str, Any]:
    if gate == "search":
        unknown = set(decision) - {"value", "probability_search"}
        if unknown:
            raise AdapterContractError(f"unknown Search decision field(s): {sorted(unknown)!r}")
        value = _string(decision.get("value"), "decision.value")
        if value not in {"search", "no_search"}:
            raise AdapterContractError(f"invalid Search decision: {value}")
        return {
            "value": value,
            "probability_search": _probability(
                decision.get("probability_search"), "decision.probability_search"
            ),
        }

    if gate == "model_tier":
        unknown = set(decision) - {"value", "difficulty_score", "probability_strong"}
        if unknown:
            raise AdapterContractError(
                f"unknown Model Tier decision field(s): {sorted(unknown)!r}"
            )
        value = _string(decision.get("value"), "decision.value")
        if value not in {"fast", "strong"}:
            raise AdapterContractError(f"invalid Model Tier decision: {value}")
        return {
            "value": value,
            "difficulty_score": _number(
                decision.get("difficulty_score"), "decision.difficulty_score"
            ),
            "probability_strong": _probability(
                decision.get("probability_strong"), "decision.probability_strong"
            ),
        }

    if gate == "notification":
        unknown = set(decision) - {"value", "notify_now", "priority_score"}
        if unknown:
            raise AdapterContractError(
                f"unknown Notification decision field(s): {sorted(unknown)!r}"
            )
        value = _string(decision.get("value"), "decision.value")
        if value not in {"silent", "digest", "notify_now"}:
            raise AdapterContractError(f"invalid Notification decision: {value}")
        notify_now = decision.get("notify_now")
        if not isinstance(notify_now, bool):
            raise AdapterContractError("decision.notify_now must be boolean")
        return {
            "value": value,
            "notify_now": notify_now,
            "priority_score": _number(
                decision.get("priority_score"), "decision.priority_score"
            ),
        }

    if gate == "completion":
        allowed = {
            "value",
            "probability_complete",
            "probability_verify",
            "probability_continue",
        }
        unknown = set(decision) - allowed
        if unknown:
            raise AdapterContractError(
                f"unknown Completion decision field(s): {sorted(unknown)!r}"
            )
        value = _string(decision.get("value"), "decision.value")
        if value not in {"complete", "continue", "verify"}:
            raise AdapterContractError(f"invalid Completion decision: {value}")
        return {
            "value": value,
            "probability_complete": _probability(
                decision.get("probability_complete"), "decision.probability_complete"
            ),
            "probability_verify": _probability(
                decision.get("probability_verify"), "decision.probability_verify"
            ),
            "probability_continue": _probability(
                decision.get("probability_continue"), "decision.probability_continue"
            ),
        }

    if gate == "retry_escalation":
        allowed = {"value", "raw_model_decision", "safety_override_reason"}
        unknown = set(decision) - allowed
        if unknown:
            raise AdapterContractError(f"unknown Retry decision field(s): {sorted(unknown)!r}")
        # Required-but-nullable is different from optional. A missing key
        # must not be silently normalized to JSON null.
        missing = allowed - set(decision)
        if missing:
            raise AdapterContractError(f"missing Retry decision field(s): {sorted(missing)!r}")
        value = _string(decision["value"], "decision.value")
        options = {"retry_same", "try_alternative", "escalate_model", "verify_state", "ask_user", "abort"}
        if value not in options:
            raise AdapterContractError(f"invalid Retry decision: {value}")
        raw = _string(decision.get("raw_model_decision"), "decision.raw_model_decision", nullable=True)
        if raw is not None and raw not in options:
            raise AdapterContractError("invalid Retry raw_model_decision")
        override = _string(decision.get("safety_override_reason"), "decision.safety_override_reason", nullable=True)
        return {"value": value, "raw_model_decision": raw, "safety_override_reason": override}

    raise AdapterContractError(f"unknown gate: {gate}")


def envelope_from_runtime(gate: GateName, payload: Any) -> DecisionEnvelope:
    """Normalize the current Runtime workflow response without changing its API."""

    record = _record(payload, "runtime decision")
    if "request_id" not in record:
        raise AdapterContractError("missing runtime decision field: request_id")
    common: dict[str, Any] = {
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "request_id": record["request_id"],
        "gate": gate,
        "decision_source": record.get("decision_source"),
        "reason": record.get("reason"),
        "backend": record.get("backend"),
        "latency_ms": record.get("latency_ms"),
        "metadata": {
            key: record[key]
            for key in ("workflow", "route_reason", "token_count")
            if key in record
        },
    }
    if "confidence" in record:
        common["confidence"] = record["confidence"]
    if gate == "search":
        common["decision"] = {
            "value": record.get("decision"),
            "probability_search": record.get("probability_search"),
        }
    elif gate == "model_tier":
        common["decision"] = {
            "value": record.get("tier"),
            "difficulty_score": record.get("difficulty_score"),
            "probability_strong": record.get("probability_strong"),
        }
    elif gate == "notification":
        common["decision"] = {
            "value": record.get("delivery"),
            "notify_now": record.get("notify_now"),
            "priority_score": record.get("priority_score"),
        }
    elif gate == "completion":
        common["decision"] = {
            "value": record.get("decision"),
            "probability_complete": record.get("probability_complete"),
            "probability_verify": record.get("probability_verify"),
            "probability_continue": record.get("probability_continue"),
        }
    elif gate == "retry_escalation":
        # Preserve presence at the wire boundary too: .get() here would
        # fabricate nullable fields and defeat the strict envelope validator.
        required = {
            "decision", "guarded_decision", "raw_model_decision",
            "safety_override_reason", "advisory_only",
        }
        missing = required - set(record)
        if missing:
            raise AdapterContractError(f"missing Retry runtime field(s): {sorted(missing)!r}")
        if record["advisory_only"] is not True:
            raise AdapterContractError("Retry runtime must be advisory_only")
        if record["decision"] != record["guarded_decision"]:
            raise AdapterContractError("Retry runtime decision and guard disagree")
        common["decision"] = {
            "value": record["guarded_decision"],
            "raw_model_decision": record["raw_model_decision"],
            "safety_override_reason": record["safety_override_reason"],
        }
        common["metadata"]["advisory_only"] = True
    else:  # pragma: no cover - typing prevents normal callers from reaching this.
        raise AdapterContractError(f"unknown gate: {gate}")
    return validate_decision_envelope(common)
