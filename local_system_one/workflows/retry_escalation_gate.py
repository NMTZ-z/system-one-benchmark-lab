"""Structured, advisory-only Retry / Escalation Gate.

No exception strings, traces, prompts, credentials or tool arguments may enter this gate.
The caller owns recovery permissions, budgets, delays and all actual actions.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from ..engine import DecisionEngine
from ..metrics import error_accounting_scope, record_error_once
from ..schemas import DecisionRequest

DECISIONS = (
    "retry_same", "try_alternative", "escalate_model",
    "verify_state", "ask_user", "abort",
)
CATEGORIES = frozenset((
    "timeout", "network", "rate_limit", "server_error", "auth",
    "validation", "tool_error", "test_failure", "logic_failure",
    "partial_success", "unknown",
))
OPERATIONS = frozenset((
    "read", "write", "remote_api", "local_file", "git_push",
    "pr_create", "test", "compute", "unknown",
))
MAX_REQUEST_ID = 128
MAX_ATTEMPTS = 50
MAX_RETRY_AFTER_MS = 3_600_000
# These HTTP client responses can be transient with verified caller evidence;
# this allowlist does not by itself authorize a retry or any Agent action.
POTENTIALLY_RETRYABLE_HTTP_4XX = frozenset({408, 425, 429})


def _choice(record: dict[str, Any], key: str, values: frozenset[str], *, default: str | None = None) -> str:
    value = record.get(key, default)
    if not isinstance(value, str) or value not in values:
        raise ValueError(f"{key} must be one of {sorted(values)}")
    return value


def _boolean(record: dict[str, Any], key: str, *, default: bool | None = None) -> bool:
    value = record.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _int(record: dict[str, Any], key: str, *, minimum: int = 0, maximum: int = 100_000,
         default: int | None = None) -> int:
    value = record.get(key, default)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{key} must be an integer in [{minimum}, {maximum}]")
    return value


def _record(payload: dict[str, Any], key: str, fields: set[str]) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be an object")
    unknown = value.keys() - fields
    if unknown:
        raise ValueError(f"unknown {key} field(s): {sorted(unknown)!r}")
    return value


@dataclass(frozen=True)
class RetryEscalationRequest:
    failure: dict[str, Any]
    operation: dict[str, Any]
    history: dict[str, Any]
    constraints: dict[str, Any]
    request_id: str | None = None
    backend: str = "auto"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RetryEscalationRequest":
        if not isinstance(payload, dict):
            raise TypeError("payload must be an object")
        if payload.keys() - {"failure", "operation", "history", "constraints", "request_id", "backend"}:
            raise ValueError("unexpected top-level field; raw traces and free-form messages are not accepted")
        request_id = payload.get("request_id")
        if request_id is not None and (
            not isinstance(request_id, str) or not request_id or len(request_id) > MAX_REQUEST_ID
        ):
            raise ValueError("request_id must be a bounded string")
        backend = _choice(payload, "backend", frozenset({"auto", "mlx", "ane"}), default="auto")

        failure = _record(payload, "failure", {
            "category", "transience", "outcome_known", "http_status", "retry_after_ms",
        })
        category = _choice(failure, "category", CATEGORIES)
        transience = _choice(failure, "transience", frozenset({"transient", "permanent", "unknown"}))
        outcome_known = _boolean(failure, "outcome_known")
        status = failure.get("http_status")
        if status is not None:
            status = _int(failure, "http_status", minimum=100, maximum=599)
        retry_after = failure.get("retry_after_ms")
        if retry_after is not None:
            retry_after = _int(failure, "retry_after_ms", maximum=MAX_RETRY_AFTER_MS)
        # Category/status contradictions are deliberately rejected instead of second-guessing.
        if status in (401, 403) and category != "auth":
            raise ValueError("401/403 must be categorized as auth")
        if status == 429 and category != "rate_limit":
            raise ValueError("429 must be categorized as rate_limit")
        if category == "rate_limit" and status not in (None, 429):
            raise ValueError("rate_limit cannot claim unrelated HTTP status")
        if (status is not None and 400 <= status < 500
            and status not in POTENTIALLY_RETRYABLE_HTTP_4XX
            and status not in {401, 403}  # existing auth hard rule takes precedence
            and transience == "transient"):
            # Do not accept client-side errors (400/404/409/422 etc.) as a
            # transient network problem simply because a caller claims it.
            raise ValueError("non-retryable HTTP client-error status cannot be transient")
        failure_out = {
            "category": category,
            "transience": transience,
            "outcome_known": outcome_known,
            "http_status": status,
            "retry_after_ms": retry_after,
        }

        operation = _record(payload, "operation", {
            "type", "side_effect", "idempotency", "side_effect_status",
            "verified_idempotency_key", "reversibility", "metadata_source",
        })
        op_type = _choice(operation, "type", OPERATIONS)
        side_effect = _choice(operation, "side_effect", frozenset({"none", "write", "external", "unknown"}))
        # The operation type is an independent trusted dimension, not an alias
        # for the caller-supplied side-effect flag. A contradictory "read"
        # classification on a mutating tool must never enable retry_same.
        # "write" and "external" are both mutating classifications. They
        # remain conservative for remote operations without requiring an exact
        # locality distinction; the already-frozen synthetic corpus includes
        # remote writes labeled "write".
        if op_type in {"write", "git_push", "pr_create"} and side_effect == "none":
            raise ValueError(f"operation.type {op_type} conflicts with side_effect")
        idempotency = _choice(operation, "idempotency",
                              frozenset({"verified", "non_idempotent", "unknown"}))
        side_status = _choice(operation, "side_effect_status",
                              frozenset({"none", "applied", "not_applied", "partial", "unknown"}))
        verified_key = _boolean(operation, "verified_idempotency_key", default=False)
        reversibility = _choice(operation, "reversibility",
                                frozenset({"yes", "no", "unknown"}), default="unknown")
        source = _choice(operation, "metadata_source",
                         frozenset({"adapter_policy", "unknown"}), default="unknown")
        if source == "unknown" and (side_effect == "none" or idempotency == "verified"):
            # Proven read/idempotency must be a trusted platform/tool policy,
            # not a guess based on a tool's error message.
            raise ValueError("verified operation guarantees require adapter_policy metadata_source")
        if side_effect == "none" and side_status not in {"none", "not_applied"}:
            raise ValueError("read/no-side-effect operations cannot have applied side effects")
        if verified_key and idempotency != "verified":
            raise ValueError("verified key requires verified idempotency")
        operation_out = {
            "type": op_type,
            "side_effect": side_effect,
            "idempotency": idempotency,
            "side_effect_status": side_status,
            "verified_idempotency_key": verified_key,
            "reversibility": reversibility,
            "metadata_source": source,
        }

        history = _record(payload, "history", {
            "attempts", "max_attempts", "repeated_failures", "remaining_time_ms",
            "retry_budget_available",
        })
        attempts = _int(history, "attempts", maximum=MAX_ATTEMPTS)
        max_attempts = None if history.get("max_attempts") is None else _int(history, "max_attempts", minimum=1, maximum=MAX_ATTEMPTS)
        repeats = _int(history, "repeated_failures", default=0, maximum=MAX_ATTEMPTS)
        remaining = None if history.get("remaining_time_ms") is None else _int(history, "remaining_time_ms", maximum=86_400_000)
        retry_budget = _boolean(history, "retry_budget_available", default=False)
        history_out = {
            "attempts": attempts,
            "max_attempts": max_attempts,
            "repeated_failures": repeats,
            "remaining_time_ms": remaining,
            "retry_budget_available": retry_budget,
        }

        constraints = _record(payload, "constraints", {
            "requires_approval", "escalation_allowed", "escalation_budget_available",
            "alternative_available",
        })
        constraints_out = {
            key: _boolean(constraints, key, default=False)
            for key in (
                "requires_approval", "escalation_allowed",
                "escalation_budget_available", "alternative_available",
            )
        }
        return cls(failure_out, operation_out, history_out, constraints_out, request_id, backend)


class RetryEscalationGate:
    """Rule-first, model-second: return an advisory label and guarded evidence only."""

    def __init__(self, engine: DecisionEngine | None = None):
        self.engine = engine

    @staticmethod
    def _can_retry(req: RetryEscalationRequest) -> bool:
        h, o, c = req.history, req.operation, req.constraints
        if (c["requires_approval"] or not h["retry_budget_available"] or
            (h["remaining_time_ms"] is None or h["remaining_time_ms"] == 0) or
            (h["max_attempts"] is None or h["attempts"] >= h["max_attempts"])):
            return False
        if o["metadata_source"] != "adapter_policy" or o["idempotency"] == "non_idempotent":
            return False
        # An unknown side-effect classification is not a verified safety fact,
        # even if the caller separately claims an idempotency key.
        if o["side_effect"] == "unknown":
            return False
        if o["side_effect"] == "none":
            return True
        # Verified idempotency alone is insufficient for an unverified write outcome;
        # only a confirmed non-execution permits retry in this phase.
        return (o["idempotency"] == "verified" and
                o["side_effect_status"] == "not_applied" and
                o["verified_idempotency_key"])

    def _resolve_rules(self, req: RetryEscalationRequest) -> tuple[str | None, str, list[str]]:
        f, o, h, c = req.failure, req.operation, req.history, req.constraints
        if (o["side_effect"] != "none" and
            (o["side_effect_status"] in {"unknown", "partial"} or not f["outcome_known"])):
            return "verify_state", "unconfirmed_side_effect_verify_first", ["verify_state"]
        if o["side_effect"] != "none" and o["side_effect_status"] == "applied":
            return "abort", "side_effect_already_applied_no_duplicate_action", ["abort"]
        if c["requires_approval"]:
            return "ask_user", "approval_required", ["ask_user"]
        if f["category"] == "auth" or f["http_status"] in {401, 403}:
            return "ask_user", "permission_error_not_retryable", ["ask_user"]
        status = f["http_status"]
        if (status is not None and 400 <= status < 500
            and status not in POTENTIALLY_RETRYABLE_HTTP_4XX):
            # A non-transient client error cannot become retry_same even
            # when the user-supplied category is tool_error or unknown.
            return "ask_user", "http_client_error_not_retryable", ["ask_user"]
        if ((h["max_attempts"] is not None and h["attempts"] >= h["max_attempts"]) or
            h["remaining_time_ms"] == 0):
            # This is aborting the *recovery path*, not the native Agent.
            return "abort", "recovery_budget_exhausted", ["abort"]
        if not h["retry_budget_available"] or h["max_attempts"] is None or h["remaining_time_ms"] is None:
            return "ask_user", "retry_budget_unverified", ["ask_user"]
        if f["category"] == "rate_limit":
            if f["transience"] == "permanent":
                return "ask_user", "permanent_rate_limit_not_retryable", ["ask_user"]
            # A 429 Retry-After is *not* an exemption from the general
            # transient-failure repetition cap. Both conditions must hold
            # before we can even advise the caller to retry.
            if (f["transience"] == "transient" and h["repeated_failures"] < 2
                and self._can_retry(req) and f["retry_after_ms"] is not None
                and f["retry_after_ms"] <= h["remaining_time_ms"]):
                return "retry_same", "rate_limit_wait_required_by_caller", ["retry_same"]
            return "ask_user", "rate_limit_delay_or_budget_unavailable", ["ask_user"]
        if f["category"] == "validation":
            return "ask_user", "validation_requires_corrected_input", ["ask_user"]
        if f["category"] == "partial_success":
            return "verify_state", "partial_effect_requires_reconciliation", ["verify_state"]
        if f["transience"] == "permanent" and not c["alternative_available"]:
            return "abort", "permanent_failure_no_alternative", ["abort"]

        # Make candidate space explicit. Laya may only classify these SAFE options.
        choices: list[str] = []
        if f["transience"] == "transient" and self._can_retry(req) and h["repeated_failures"] < 2:
            choices.append("retry_same")
        if c["alternative_available"]:
            choices.append("try_alternative")
        if (f["category"] in {"tool_error", "test_failure", "logic_failure"} and
            c["escalation_allowed"] and c["escalation_budget_available"]):
            choices.append("escalate_model")
        choices.append("ask_user")
        if f["transience"] == "permanent":
            choices.append("abort")
        if len(choices) == 1:
            return choices[0], "single_safe_rule_candidate", choices
        return None, "multiple_safe_recovery_options", choices

    @staticmethod
    def _output(
        req: RetryEscalationRequest, decision: str, source: str, reason: str,
        *, raw: str | None = None, probabilities: dict[str, float] | None = None,
        confidence: float = 1.0, backend: str = "rule", route_reason: str = "deterministic",
        latency_ms: float = 0.0, token_count: int = 0, override: str | None = None,
    ) -> dict[str, Any]:
        return {
            "workflow": "retry_escalation_gate",
            "decision": decision,
            "guarded_decision": decision,
            "raw_model_decision": raw,
            "safety_override_reason": override,
            "decision_source": source,
            "reason": reason,
            "probabilities": probabilities,
            "confidence": confidence,
            "backend": backend,
            "route_reason": route_reason,
            "latency_ms": round(latency_ms, 3),
            "token_count": token_count,
            "request_id": req.request_id,
            "advisory_only": True,
        }

    def _rule_result(
        self,
        req: RetryEscalationRequest,
        decision: str,
        reason: str,
        *,
        started: float,
        raw: str | None = None,
        probabilities: dict[str, float] | None = None,
        override: str | None = None,
        record_metric: bool = True,
    ) -> dict[str, Any]:
        """Account for a rule-only request without double-counting model inference."""
        latency_ms = (time.perf_counter() - started) * 1000
        route_reason = f"retry_escalation_gate:{reason}"
        metrics = getattr(self.engine, "metrics", None)
        if record_metric and metrics is not None:
            metrics.record(backend="rule", route_reason=route_reason, latency_ms=latency_ms)
        return self._output(
            req, decision, "rule", reason,
            raw=raw, probabilities=probabilities, override=override,
            backend="rule", route_reason=route_reason, latency_ms=latency_ms,
        )

    def decide(self, req: RetryEscalationRequest) -> dict[str, Any]:
        # Share the error marker with nested DecisionEngine.decide() so a
        # backend failure counts once when called directly, over HTTP, or
        # through another workflow.
        with error_accounting_scope():
            return self._decide_in_scope(req)

    def _decide_in_scope(self, req: RetryEscalationRequest) -> dict[str, Any]:
        started = time.perf_counter()
        forced, reason, candidates = self._resolve_rules(req)
        if forced is not None:
            return self._rule_result(req, forced, reason, started=started)

        # Without an authenticated, local decision backend we preserve the
        # deterministic fallback; there is never implied Agent execution authority.
        fallback = "try_alternative" if "try_alternative" in candidates else "ask_user"
        if self.engine is None:
            return self._rule_result(
                req, fallback, "model_unavailable_rule_only", started=started,
            )
        state = {
            "failure": {key: req.failure[key] for key in ("category", "transience", "outcome_known")},
            "operation": {
                key: req.operation[key]
                for key in ("type", "side_effect", "idempotency", "side_effect_status")
            },
            "history": {
                key: req.history[key]
                for key in ("attempts", "max_attempts", "repeated_failures")
            },
            "constraints": dict(req.constraints),
        }
        question = (
            "Select the most useful next recovery RECOMMENDATION for a failed Agent step. "
            "All actions are passive suggestions. Prefer safe alternatives to repeated failures. "
            "Do not invent permissions, idempotency, tools, or observed execution outcomes."
        )
        model_inference_completed = False
        try:
            model = self.engine.decide(DecisionRequest(
                primitive="choice", state=state, instructions=question,
                criteria=list(candidates), request_id=req.request_id,
                backend=req.backend,  # type: ignore[arg-type]
            ))
            # DecisionEngine recorded backend/latency for a completed inference.
            # A safety override must not add a second request to /metrics.
            model_inference_completed = True
            raw = str(model["decision"])
            if raw not in DECISIONS:
                raise ValueError("invalid raw recovery choice")
            supplied = model.get("probabilities")
            if not isinstance(supplied, dict) or any(
                isinstance(supplied.get(candidate), bool) or
                not isinstance(supplied.get(candidate), (int, float)) or
                not math.isfinite(float(supplied[candidate])) or
                not 0 <= float(supplied[candidate]) <= 1
                for candidate in candidates
            ):
                raise ValueError("invalid model recovery distribution")
            scores = {key: float(supplied[key]) for key in candidates}
            if not 0.95 <= sum(scores.values()) <= 1.05:
                raise ValueError("model probability mass invalid")
            confidence = float(model["confidence"])
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("invalid model confidence")
            if raw not in candidates:
                return self._output(
                    req, fallback, "rule", "model_choice_blocked_by_safety",
                    raw=raw, override="raw_model_decision_not_permitted",
                    probabilities=scores, latency_ms=(time.perf_counter() - started) * 1000,
                )
            return self._output(
                req, raw, "model", f"model_{raw}", raw=raw,
                probabilities=scores, confidence=confidence,
                backend=str(model["backend"]), route_reason=str(model["route_reason"]),
                latency_ms=(time.perf_counter() - started) * 1000,
                token_count=int(model["token_count"]),
            )
        except Exception as error:  # noqa: BLE001 - safe fail-open at recovery classifier boundary
            if hasattr(self.engine, "metrics"):
                record_error_once(self.engine.metrics, error)
            return self._rule_result(
                req, fallback, "inference_failed_rule_fallback",
                started=started, override="model_or_backend_failure",
                record_metric=not model_inference_completed,
            )
