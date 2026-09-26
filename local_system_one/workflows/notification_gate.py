"""Notification gate for deciding whether an agent event should interrupt the user."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..engine import DecisionEngine
from ..schemas import DecisionRequest

Urgency = Literal["auto", "low", "medium", "high", "critical"]
Delivery = Literal["silent", "digest", "notify_now"]


@dataclass(frozen=True)
class NotificationGateRequest:
    event: str
    context: Any = None
    urgency: Urgency = "auto"
    user_action_required: bool = False
    blocking_failure: bool = False
    routine_update: bool = False
    deadline_minutes: int | None = None
    request_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> NotificationGateRequest:
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        event = payload.get("event")
        if not isinstance(event, str) or not event.strip():
            raise ValueError("event must be a non-empty string")

        urgency = payload.get("urgency", "auto")
        if urgency not in {"auto", "low", "medium", "high", "critical"}:
            raise ValueError("urgency must be auto, low, medium, high, or critical")

        for key in ("user_action_required", "blocking_failure", "routine_update"):
            if not isinstance(payload.get(key, False), bool):
                raise TypeError(f"{key} must be boolean")

        deadline = payload.get("deadline_minutes")
        if deadline is not None:
            if not isinstance(deadline, int):
                raise TypeError("deadline_minutes must be an integer when provided")
            if deadline < 0:
                raise ValueError("deadline_minutes cannot be negative")

        request_id = payload.get("request_id")
        if request_id is not None and not isinstance(request_id, str):
            raise TypeError("request_id must be a string when provided")

        return cls(
            event=event.strip(),
            context=payload.get("context"),
            urgency=urgency,
            user_action_required=payload.get("user_action_required", False),
            blocking_failure=payload.get("blocking_failure", False),
            routine_update=payload.get("routine_update", False),
            deadline_minutes=deadline,
            request_id=request_id,
        )


class NotificationGate:
    """Three-level notification policy with safety hard gates."""

    def __init__(
        self,
        engine: DecisionEngine,
        *,
        digest_score_threshold: float = 1.25,
        notify_score_threshold: float = 2.75,
    ):
        if not 0.0 <= digest_score_threshold < notify_score_threshold <= 4.0:
            raise ValueError(
                "notification thresholds must satisfy 0 <= digest < notify <= 4"
            )
        self.engine = engine
        self.digest_score_threshold = float(digest_score_threshold)
        self.notify_score_threshold = float(notify_score_threshold)

    def _rule_result(
        self,
        delivery: Delivery,
        reason: str,
        request: NotificationGateRequest,
        *,
        priority_score: float,
    ) -> dict[str, Any]:
        self.engine.metrics.record(
            backend="rule",
            route_reason=f"notification_gate:{reason}",
            latency_ms=0.0,
        )
        return {
            "workflow": "notification_gate",
            "delivery": delivery,
            "notify_now": delivery == "notify_now",
            "decision_source": "rule",
            "reason": reason,
            "priority_score": priority_score,
            "confidence": 1.0,
            "backend": "rule",
            "route_reason": f"notification_gate:{reason}",
            "token_count": 0,
            "latency_ms": 0.0,
            "request_id": request.request_id,
            "ane_health": self.engine.health.snapshot().as_dict(),
        }

    def _hard_gate(self, request: NotificationGateRequest) -> dict[str, Any] | None:
        if request.urgency == "critical":
            return self._rule_result(
                "notify_now", "urgency_critical", request, priority_score=4.0
            )

        if request.blocking_failure:
            return self._rule_result(
                "notify_now", "blocking_failure", request, priority_score=4.0
            )

        if request.deadline_minutes is not None and request.deadline_minutes <= 30:
            return self._rule_result(
                "notify_now", "near_deadline", request, priority_score=4.0
            )

        if request.user_action_required and request.urgency in {"high", "critical"}:
            return self._rule_result(
                "notify_now", "urgent_user_action", request, priority_score=4.0
            )

        if (
            request.routine_update
            and not request.user_action_required
            and request.urgency in {"auto", "low"}
        ):
            return self._rule_result(
                "digest", "routine_update", request, priority_score=1.0
            )

        return None

    def decide(self, request: NotificationGateRequest) -> dict[str, Any]:
        hard = self._hard_gate(request)
        if hard is not None:
            return hard

        state = {
            "event": request.event,
            "context": request.context,
            "urgency": request.urgency,
            "user_action_required": request.user_action_required,
            "blocking_failure": request.blocking_failure,
            "routine_update": request.routine_update,
            "deadline_minutes": request.deadline_minutes,
        }
        primitive = DecisionRequest(
            primitive="score",
            state=state,
            instructions=(
                "How important is it to interrupt the user about this agent event? "
                "Consider urgency, user action required, blocking impact, deadline, "
                "novelty and whether the information can wait for a digest."
            ),
            criteria=[
                "no user value; keep silent",
                "low value; log or include in a later digest",
                "useful but not urgent; include in a digest",
                "important; notify the user soon",
                "urgent or blocking; interrupt the user now",
            ],
            request_id=request.request_id,
        )
        model = self.engine.decide(primitive)
        priority_score = float(model["decision"])

        if priority_score >= self.notify_score_threshold:
            delivery: Delivery = "notify_now"
            reason = "model_priority_notify"
        elif priority_score >= self.digest_score_threshold:
            delivery = "digest"
            reason = "model_priority_digest"
        else:
            delivery = "silent"
            reason = "model_priority_silent"

        return {
            "workflow": "notification_gate",
            "delivery": delivery,
            "notify_now": delivery == "notify_now",
            "decision_source": "model",
            "reason": reason,
            "priority_score": priority_score,
            "confidence": float(model["confidence"]),
            "score_probabilities": model["probabilities"],
            "backend": model["backend"],
            "route_reason": model["route_reason"],
            "token_count": model["token_count"],
            "latency_ms": model["latency_ms"],
            "request_id": request.request_id,
            "ane_health": model["ane_health"],
        }