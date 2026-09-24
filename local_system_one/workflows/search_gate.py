"""Health-aware Search Gate for deciding whether an agent should use the web."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from ..engine import DecisionEngine
from ..schemas import DecisionRequest

Freshness = Literal["auto", "current", "recent", "static"]
SourceScope = Literal["auto", "public", "provided_only", "local_private"]

_CURRENT_PATTERNS = (
    r"\b(today|tonight|currently|current|latest|recent|now|this week|this month)\b",
    r"\b(weather|forecast|score|standings|stock price|exchange rate|open now)\b",
    r"(今天|今晚|当前|现在|最新|最近|本周|本月|天气|预报|比分|排名|股价|汇率|营业)",
)

_VOLATILE_FACT_PATTERNS = (
    r"\b(ceo|cto|cfo|president|prime minister|mayor|chairman)\s+of\b",
    r"\bwho\s+is\s+(?:the\s+)?(?:ceo|cto|cfo|president|prime minister|mayor|chairman)\b",
    r"\b(price|pricing|availability|opening hours|business hours|service status)\b",
    r"(?:CEO|CTO|CFO|首席执行官|总裁|总统|总理|市长|董事长).*(?:是谁|叫什么|哪位)",
    r"(?:谁是|哪位是).*(?:CEO|CTO|CFO|首席执行官|总裁|总统|总理|市长|董事长)",
    r"(价格|售价|有没有货|是否有货|营业时间|服务状态|运行状态)",
)

_PROVIDED_ONLY_PATTERNS = (
    r"\b(rewrite|rephrase|proofread|translate|summarize the following|fix grammar)\b",
    r"(润色|改写|翻译|校对|总结以下|修改语法)",
)


@dataclass(frozen=True)
class SearchGateRequest:
    task: str
    context: Any = None
    freshness: Freshness = "auto"
    source_scope: SourceScope = "auto"
    external_lookup_required: bool = False
    provided_context_sufficient: bool = False
    request_id: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SearchGateRequest:
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        task = payload.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("task must be a non-empty string")

        freshness = payload.get("freshness", "auto")
        if freshness not in {"auto", "current", "recent", "static"}:
            raise ValueError("freshness must be auto, current, recent, or static")

        source_scope = payload.get("source_scope", "auto")
        if source_scope not in {"auto", "public", "provided_only", "local_private"}:
            raise ValueError(
                "source_scope must be auto, public, provided_only, or local_private"
            )

        for key in ("external_lookup_required", "provided_context_sufficient"):
            value = payload.get(key, False)
            if not isinstance(value, bool):
                raise TypeError(f"{key} must be boolean")

        request_id = payload.get("request_id")
        if request_id is not None and not isinstance(request_id, str):
            raise TypeError("request_id must be a string when provided")

        return cls(
            task=task.strip(),
            context=payload.get("context"),
            freshness=freshness,
            source_scope=source_scope,
            external_lookup_required=payload.get("external_lookup_required", False),
            provided_context_sufficient=payload.get(
                "provided_context_sufficient", False
            ),
            request_id=request_id,
        )


class SearchGate:
    """Conservative search policy with deterministic hard gates and model fallback."""

    def __init__(
        self, engine: DecisionEngine, *, no_search_max_probability: float = 0.40
    ):
        if not 0.0 <= no_search_max_probability < 0.5:
            raise ValueError("no_search_max_probability must be in [0, 0.5)")
        self.engine = engine
        self.no_search_max_probability = no_search_max_probability

    @staticmethod
    def _matches(patterns: tuple[str, ...], text: str) -> bool:
        return any(
            re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns
        )

    def _hard_gate(self, request: SearchGateRequest) -> dict[str, Any] | None:
        if request.external_lookup_required:
            return self._rule_result(True, "explicit_external_lookup_required", request)

        if request.freshness in {"current", "recent"}:
            return self._rule_result(True, f"freshness_{request.freshness}", request)

        if request.source_scope == "public" and self._matches(
            _CURRENT_PATTERNS, request.task
        ):
            return self._rule_result(True, "public_current_language", request)

        if request.source_scope in {"provided_only", "local_private"}:
            return self._rule_result(
                False, f"source_scope_{request.source_scope}", request
            )

        if request.provided_context_sufficient:
            return self._rule_result(False, "provided_context_sufficient", request)

        if request.freshness == "static" and self._matches(
            _PROVIDED_ONLY_PATTERNS, request.task
        ):
            return self._rule_result(False, "static_transform_task", request)

        if self._matches(_CURRENT_PATTERNS, request.task):
            return self._rule_result(True, "current_language", request)

        if self._matches(_VOLATILE_FACT_PATTERNS, request.task):
            return self._rule_result(True, "volatile_public_fact", request)

        return None

    def _rule_result(
        self,
        should_search: bool,
        reason: str,
        request: SearchGateRequest,
    ) -> dict[str, Any]:
        self.engine.metrics.record(
            backend="rule",
            route_reason=f"search_gate:{reason}",
            latency_ms=0.0,
        )
        return {
            "workflow": "search_gate",
            "should_search": should_search,
            "decision": "search" if should_search else "no_search",
            "decision_source": "rule",
            "reason": reason,
            "probability_search": 1.0 if should_search else 0.0,
            "confidence": 1.0,
            "backend": "rule",
            "route_reason": f"search_gate:{reason}",
            "token_count": 0,
            "latency_ms": 0.0,
            "request_id": request.request_id,
            "ane_health": self.engine.health.snapshot().as_dict(),
        }

    def decide(self, request: SearchGateRequest) -> dict[str, Any]:
        hard = self._hard_gate(request)
        if hard is not None:
            return hard

        state = {
            "task": request.task,
            "context": request.context,
            "freshness_requirement": request.freshness,
            "source_scope": request.source_scope,
            "provided_context_sufficient": request.provided_context_sufficient,
        }
        primitive = DecisionRequest(
            primitive="noul",
            state=state,
            instructions=(
                "Does answering this task correctly require looking up information "
                "outside the provided state, such as current public facts, recent "
                "events, live data, an external page, or information not supplied here?"
            ),
            request_id=request.request_id,
        )
        model = self.engine.decide(primitive)
        probability_search = float(model["probabilities"]["true"])

        # False negatives are more costly than an unnecessary search. Only suppress
        # search when the model is clearly on the no-search side.
        should_search = probability_search > self.no_search_max_probability
        if should_search and probability_search < 0.5:
            reason = "model_uncertain_conservative_search"
        elif should_search:
            reason = "model_requires_external_information"
        else:
            reason = "model_confident_local_answer"

        return {
            "workflow": "search_gate",
            "should_search": should_search,
            "decision": "search" if should_search else "no_search",
            "decision_source": "model",
            "reason": reason,
            "probability_search": probability_search,
            "confidence": float(model["confidence"]),
            "backend": model["backend"],
            "route_reason": model["route_reason"],
            "token_count": model["token_count"],
            "latency_ms": model["latency_ms"],
            "request_id": request.request_id,
            "ane_health": model["ane_health"],
        }
