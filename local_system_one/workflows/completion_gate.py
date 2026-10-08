"""Completion gate for deciding whether an agent task may stop, continue, or verify."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..engine import DecisionEngine
from ..schemas import DecisionRequest

CompletionDecision = Literal["complete", "continue", "verify"]

MAX_TASK_CHARS = 4_000
MAX_RESULT_CHARS = 6_000
MAX_REQUEST_ID_CHARS = 256

_EXECUTION_FIELDS = {
    "tools_used",
    "tool_failures",
    "tests_run",
    "tests_passed",
    "artifacts_created",
    "required_checks_completed",
    "required_artifact_missing",
    "required_step_missing",
    "blocking_failure",
    "conflicting_evidence",
    "verification_required",
    "final_state_verified",
}
_COUNT_FIELDS = {
    "tools_used",
    "tool_failures",
    "tests_run",
    "tests_passed",
    "artifacts_created",
}


def _bounded_text(value: Any, field: str, limit: int) -> tuple[str, bool]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    text = value.strip()
    if len(text) <= limit:
        return text, False
    marker = "\n[truncated]"
    return text[: max(1, limit - len(marker))] + marker, True


def _execution_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("execution_state must be an object")
    unknown = set(value) - _EXECUTION_FIELDS
    if unknown:
        raise ValueError(f"unknown execution_state field(s): {sorted(unknown)!r}")

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key in _COUNT_FIELDS:
            if not isinstance(item, int) or isinstance(item, bool) or item < 0:
                raise TypeError(f"execution_state.{key} must be a non-negative integer")
            normalized[key] = item
        else:
            if not isinstance(item, bool):
                raise TypeError(f"execution_state.{key} must be boolean")
            normalized[key] = item

    tests_run = normalized.get("tests_run")
    tests_passed = normalized.get("tests_passed")
    if tests_run is not None and tests_passed is not None and tests_passed > tests_run:
        raise ValueError("execution_state.tests_passed cannot exceed tests_run")
    return normalized


@dataclass(frozen=True)
class CompletionGateRequest:
    task: str
    current_result: str
    execution_state: dict[str, Any]
    request_id: str | None = None
    task_truncated: bool = False
    result_truncated: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CompletionGateRequest:
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        allowed = {"task", "current_result", "execution_state", "request_id"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown completion request field(s): {sorted(unknown)!r}")

        task, task_truncated = _bounded_text(payload.get("task"), "task", MAX_TASK_CHARS)
        result, result_truncated = _bounded_text(
            payload.get("current_result"), "current_result", MAX_RESULT_CHARS
        )
        state = _execution_state(payload.get("execution_state"))

        request_id = payload.get("request_id")
        if request_id is not None:
            if not isinstance(request_id, str) or not request_id:
                raise TypeError("request_id must be a non-empty string when provided")
            if len(request_id) > MAX_REQUEST_ID_CHARS:
                raise ValueError(f"request_id cannot exceed {MAX_REQUEST_ID_CHARS} characters")

        return cls(
            task=task,
            current_result=result,
            execution_state=state,
            request_id=request_id,
            task_truncated=task_truncated,
            result_truncated=result_truncated,
        )


class CompletionGate:
    """Conservative three-way completion classifier."""

    def __init__(self, engine: DecisionEngine, *, min_complete_probability: float = 0.70):
        if not 0.5 <= min_complete_probability <= 1.0:
            raise ValueError("min_complete_probability must be in [0.5, 1.0]")
        self.engine = engine
        self.min_complete_probability = float(min_complete_probability)

    def _result(
        self,
        *,
        decision: CompletionDecision,
        source: Literal["rule", "model"],
        reason: str,
        probabilities: dict[str, float],
        confidence: float,
        backend: str,
        route_reason: str,
        token_count: int,
        latency_ms: float,
        request: CompletionGateRequest,
    ) -> dict[str, Any]:
        return {
            "workflow": "completion_gate",
            "decision": decision,
            "decision_source": source,
            "reason": reason,
            "probability_complete": float(probabilities.get("complete", 0.0)),
            "probability_verify": float(probabilities.get("verify", 0.0)),
            "probability_continue": float(probabilities.get("continue", 0.0)),
            "confidence": float(confidence),
            "backend": backend,
            "route_reason": route_reason,
            "token_count": int(token_count),
            "latency_ms": float(latency_ms),
            "request_id": request.request_id,
            "input_bounded": {
                "task_truncated": request.task_truncated,
                "result_truncated": request.result_truncated,
                "task_chars": len(request.task),
                "result_chars": len(request.current_result),
            },
            "ane_health": self.engine.health.snapshot().as_dict(),
        }

    def _rule_result(
        self,
        decision: CompletionDecision,
        reason: str,
        request: CompletionGateRequest,
    ) -> dict[str, Any]:
        self.engine.metrics.record(
            backend="rule",
            route_reason=f"completion_gate:{reason}",
            latency_ms=0.0,
        )
        probabilities = {
            "complete": 1.0 if decision == "complete" else 0.0,
            "verify": 1.0 if decision == "verify" else 0.0,
            "continue": 1.0 if decision == "continue" else 0.0,
        }
        return self._result(
            decision=decision,
            source="rule",
            reason=reason,
            probabilities=probabilities,
            confidence=1.0,
            backend="rule",
            route_reason=f"completion_gate:{reason}",
            token_count=0,
            latency_ms=0.0,
            request=request,
        )

    def _hard_gate(self, request: CompletionGateRequest) -> dict[str, Any] | None:
        state = request.execution_state
        if state.get("blocking_failure"):
            return self._rule_result("continue", "blocking_failure", request)
        if state.get("required_artifact_missing"):
            return self._rule_result("continue", "required_artifact_missing", request)
        if state.get("required_step_missing"):
            return self._rule_result("continue", "required_step_missing", request)
        if state.get("required_checks_completed") is False:
            return self._rule_result("continue", "required_checks_incomplete", request)

        tests_run = state.get("tests_run")
        tests_passed = state.get("tests_passed")
        if (
            isinstance(tests_run, int)
            and isinstance(tests_passed, int)
            and tests_run > tests_passed
        ):
            return self._rule_result("continue", "explicit_test_failure", request)

        if state.get("conflicting_evidence"):
            return self._rule_result("verify", "conflicting_evidence", request)
        if state.get("verification_required") and not state.get("final_state_verified", False):
            return self._rule_result("verify", "final_state_not_verified", request)
        return None

    def decide(self, request: CompletionGateRequest) -> dict[str, Any]:
        hard = self._hard_gate(request)
        if hard is not None:
            return hard

        primitive = DecisionRequest(
            primitive="choice",
            state={
                "task": request.task,
                "current_result": request.current_result,
                "execution_state": request.execution_state,
            },
            instructions=(
                "Decide whether the user's task is actually complete. Choose 'complete' only "
                "when the result satisfies the requested deliverable and no important verification "
                "is missing. Choose 'continue' when substantive work is still missing or failed. "
                "Choose 'verify' when there is a plausible result but its final state, evidence, or "
                "required validation is not yet established. Prefer verify over an uncertain complete."
            ),
            criteria={
                "complete": "the requested task is satisfied and important checks are complete",
                "verify": "a candidate result exists but important independent validation is missing",
                "continue": "substantive requested work is missing, failed, or still in progress",
            },
            request_id=request.request_id,
        )
        try:
            model = self.engine.decide(primitive)
        except Exception:  # noqa: BLE001 - classifier failure must never silently stop the agent
            self.engine.metrics.record_error()
            return self._rule_result("continue", "model_failure_fail_open_continue", request)

        selected = str(model["decision"])
        if selected not in {"complete", "verify", "continue"}:
            return self._rule_result("continue", "invalid_model_value_fail_open_continue", request)
        probabilities = {
            key: float(model.get("probabilities", {}).get(key, 0.0))
            for key in ("complete", "verify", "continue")
        }
        decision: CompletionDecision = selected  # type: ignore[assignment]
        reason = f"model_{decision}"
        if decision == "complete" and probabilities["complete"] < self.min_complete_probability:
            decision = "verify"
            reason = "model_complete_below_safety_threshold"

        return self._result(
            decision=decision,
            source="model",
            reason=reason,
            probabilities=probabilities,
            confidence=float(model["confidence"]),
            backend=str(model["backend"]),
            route_reason=str(model["route_reason"]),
            token_count=int(model["token_count"]),
            latency_ms=float(model["latency_ms"]),
            request=request,
        )
