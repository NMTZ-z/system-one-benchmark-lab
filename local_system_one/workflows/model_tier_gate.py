"""Model-tier gate for choosing a fast or strong generative model."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from ..engine import DecisionEngine
from ..schemas import DecisionRequest

Risk = Literal["auto", "low", "medium", "high", "critical"]
TaskType = Literal[
    "auto",
    "transform",
    "simple_qa",
    "reasoning",
    "coding",
    "research",
    "planning",
]

_TRANSFORM_PATTERNS = (
    r"\b(rewrite|rephrase|proofread|translate|format|fix grammar|shorten|compress)\b",
    r"(润色|改写|翻译|校对|排版|缩短|精简|压缩|修改语法)",
)

_STRUCTURED_TRANSFORM_PATTERNS = (
    r"\b(sort|deduplicate|dedupe|normalize dates?|extract (?:the )?(?:fields?|values?)|convert .{0,24} to json|csv .{0,16} json|return exact json)\b",
    r"(排序|去重|日期.{0,8}(标准化|规范化)|提取.{0,12}(字段|信息|值)|转换成.{0,4}JSON|转成.{0,4}JSON|输出.{0,6}JSON)",
)


@dataclass(frozen=True)
class ModelTierRequest:
    task: str
    context: Any = None
    risk: Risk = "auto"
    task_type: TaskType = "auto"
    irreversible: bool = False
    requires_precision: bool = False
    request_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ModelTierRequest:
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        task = payload.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")

        risk = payload.get("risk", "auto")
        if risk not in {"auto", "low", "medium", "high", "critical"}:
            raise ValueError("risk must be auto, low, medium, high, or critical")

        task_type = payload.get("task_type", "auto")
        if task_type not in {
            "auto",
            "transform",
            "simple_qa",
            "reasoning",
            "coding",
            "research",
            "planning",
        }:
            raise ValueError("unsupported task_type")

        for key in ("irreversible", "requires_precision"):
            if not isinstance(payload.get(key, False), bool):
                raise TypeError(f"{key} must be boolean")

        request_id = payload.get("request_id")
        if request_id is not None and not isinstance(request_id, str):
            raise TypeError("request_id must be a string when provided")

        return cls(
            task=task.strip(),
            context=payload.get("context"),
            risk=risk,
            task_type=task_type,
            irreversible=payload.get("irreversible", False),
            requires_precision=payload.get("requires_precision", False),
            request_id=request_id,
        )


class ModelTierGate:
    """Conservative fast/strong model selector."""

    def __init__(self, engine: DecisionEngine, *, strong_score_threshold: float = 2.0):
        if not 0.0 <= strong_score_threshold <= 4.0:
            raise ValueError("strong_score_threshold must be in [0, 4]")
        self.engine = engine
        self.strong_score_threshold = float(strong_score_threshold)

    @staticmethod
    def _matches(patterns: tuple[str, ...], text: str) -> bool:
        return any(
            re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns
        )

    @staticmethod
    def _has_inline_payload(task: str) -> bool:
        """Return True only when the task visibly contains bounded source material.

        Hard-fast routing must not fire for an instruction such as "translate this"
        when the actual content is absent. The heuristics intentionally prefer false
        negatives over broad downgrade coverage.
        """
        text = task.strip()
        if "```" in text:
            return True
        if len([line for line in text.splitlines() if line.strip()]) >= 2:
            return True
        for marker in ("：", ":"):
            if marker in text:
                tail = text.rsplit(marker, 1)[-1].strip()
                if len(tail) >= 4:
                    return True
        return False

    def _rule_result(
        self,
        tier: Literal["fast", "strong"],
        reason: str,
        request: ModelTierRequest,
    ) -> dict[str, Any]:
        self.engine.metrics.record(
            backend="rule",
            route_reason=f"model_tier_gate:{reason}",
            latency_ms=0.0,
        )
        return {
            "workflow": "model_tier_gate",
            "tier": tier,
            "decision_source": "rule",
            "reason": reason,
            "difficulty_score": 0.0 if tier == "fast" else 4.0,
            "probability_strong": 0.0 if tier == "fast" else 1.0,
            "confidence": 1.0,
            "backend": "rule",
            "route_reason": f"model_tier_gate:{reason}",
            "token_count": 0,
            "latency_ms": 0.0,
            "request_id": request.request_id,
            "ane_health": self.engine.health.snapshot().as_dict(),
        }

    def _hard_gate(self, request: ModelTierRequest) -> dict[str, Any] | None:
        if request.risk in {"high", "critical"}:
            return self._rule_result("strong", f"risk_{request.risk}", request)

        if request.irreversible:
            return self._rule_result("strong", "irreversible_action", request)

        if request.requires_precision:
            return self._rule_result("strong", "precision_required", request)

        bounded_input = request.context is not None or self._has_inline_payload(
            request.task
        )
        transform = request.task_type == "transform" or self._matches(
            _TRANSFORM_PATTERNS, request.task
        )
        if transform and bounded_input and request.risk in {"auto", "low"}:
            return self._rule_result("fast", "bounded_transform", request)

        structured = self._matches(_STRUCTURED_TRANSFORM_PATTERNS, request.task)
        if structured and bounded_input and request.risk in {"auto", "low"}:
            return self._rule_result("fast", "bounded_structured_transform", request)

        return None

    def decide(self, request: ModelTierRequest) -> dict[str, Any]:
        hard = self._hard_gate(request)
        if hard is not None:
            return hard

        state = {
            "task": request.task,
            "context": request.context,
            "risk": request.risk,
            "task_type": request.task_type,
            "irreversible": request.irreversible,
            "requires_precision": request.requires_precision,
        }
        primitive = DecisionRequest(
            primitive="score",
            state=state,
            instructions=(
                "How much reasoning capability is needed to complete this task reliably? "
                "Judge ambiguity, multi-step reasoning, technical depth, planning, coding "
                "difficulty and error cost. Do not reward verbosity."
            ),
            criteria=[
                "routine or direct; almost no reasoning",
                "light reasoning; familiar task",
                "moderate reasoning; several constraints or steps",
                "complex reasoning; substantial technical or planning depth",
                "expert-level deep reasoning; difficult verification or synthesis",
            ],
            request_id=request.request_id,
        )
        model = self.engine.decide(primitive)
        difficulty_score = float(model["decision"])
        probabilities = model["probabilities"]
        probability_strong = sum(
            float(probabilities.get(key, 0.0)) for key in ("3", "4")
        )

        tier = "strong" if difficulty_score >= self.strong_score_threshold else "fast"
        reason = (
            "model_complexity_requires_strong"
            if tier == "strong"
            else "model_complexity_fast_sufficient"
        )

        return {
            "workflow": "model_tier_gate",
            "tier": tier,
            "decision_source": "model",
            "reason": reason,
            "difficulty_score": difficulty_score,
            "probability_strong": probability_strong,
            "confidence": float(model["confidence"]),
            "score_probabilities": probabilities,
            "backend": model["backend"],
            "route_reason": model["route_reason"],
            "token_count": model["token_count"],
            "latency_ms": model["latency_ms"],
            "request_id": request.request_id,
            "ane_health": model["ane_health"],
        }
