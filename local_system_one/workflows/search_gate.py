"""Health-aware Search Gate for deciding whether an agent should use the web."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from ..engine import DecisionEngine
from ..schemas import DecisionRequest

Freshness = Literal["auto", "current", "recent", "static"]
SourceScope = Literal["auto", "public", "provided_only", "local_private"]

_LIVE_PUBLIC_PATTERNS = (
    r"\b(weather|forecast|live score|score today|standings|stock price|exchange rate|open now|opening hours)\b",
    r"\b(latest|current|today|now)\b.{0,30}\b(version|release|price|availability|status|weather|forecast|score|standings)\b",
    r"\b(version|release|price|availability|status|weather|forecast|score|standings)\b.{0,30}\b(latest|current|today|now)\b",
    r"(天气|预报|比分|股价|汇率|营业时间|票价|油价|金价)",
    r"(最新|当前|现在|今天).{0,18}(版本|发布|价格|售价|状态|榜单|排名|天气|预报|比分|汇率|营业)",
    r"(版本|发布|价格|售价|状态|榜单|排名|天气|预报|比分|汇率|营业).{0,18}(最新|当前|现在|今天)",
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
    r"^\s*(please\s+)?(rewrite|rephrase|proofread|translate|polish|shorten|fix grammar)\b",
    r"^\s*(请)?(把|将)?[^。！？\n]{0,40}(润色|改写|翻译|校对|精简|缩短|修改语法)",
)

_EXPLICIT_PUBLIC_LOOKUP_PATTERNS = (
    r"(全网|知乎|B站|微博|GitHub Trending|热榜|官方发布|原始链接|公开来源)",
    r"\b(github trending|official release|source link|public web|news trend|reddit)\b",
    r"(证据|来源|参考资料|公开事实|公开资料).{0,24}(URL|链接|网址)",
    r"(URL|链接|网址).{0,24}(证据|来源|参考资料|公开事实|公开资料)",
    r"(核验|查验|验证|对齐|严格对齐).{0,18}官方.{0,12}(事实|参数|规则|说明|文档)",
    r"\b(search|look up|check|verify|browse|research)\b.{0,40}\b(web|internet|official docs?|official documentation|website|release notes?)\b",
    r"\b(web|internet|official docs?|official documentation|website|release notes?)\b.{0,40}\b(search|look up|check|verify|browse|research)\b",
    r"(搜索|检索|查|查询|查验|核查|验证|浏览|访问).{0,18}(官网|官方网站|官方.{0,12}文档|网页|互联网|公开资料|发布说明|release notes)",
    r"(官网|官方网站|官方文档|网页|互联网|公开资料|发布说明).{0,18}(搜索|检索|查|查询|查验|核查|验证|浏览|访问)",
)

_LOCAL_FILE_PATTERNS = (
    r"\b(read|open|inspect|check|query|search|load|use)\b.{0,30}\b(local files?|project files?|config files?|log files?|workspace)\b",
    r"\b(local files?|project files?|config files?|log files?|workspace)\b.{0,30}\b(read|open|inspect|check|query|search|load|use)\b",
    r"\b(git diff|staged changes|local repository|repository path)\b",
    r"(调用|读取|查看|检查|查询|打开|搜索|检索|使用).{0,24}(本地文件|项目文件|WPS|NAS|日志|配置文件)",
    r"(本地文件|项目文件|WPS|NAS|日志|配置文件).{0,24}(调用|读取|查看|检查|查询|打开|搜索|检索|使用)",
    r"(/Users/|本地路径|Git仓库|Git 仓库|暂存区|git diff)",
)

_CONNECTED_APP_PATTERNS = (
    r"\b(call|query|check|read|use)\b.{0,30}\b(mcp|connector|connected app)\b",
    r"(调用|读取|查看|检查|查询|使用).{0,24}(飞书|看板|数据库|mcp|xiaohongshu|lark-cli)",
    r"(飞书|看板|数据库|mcp|xiaohongshu|lark-cli).{0,24}(调用|读取|查看|检查|查询|使用)",
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
            return self._rule_result(True, "explicit_public_lookup_required", request)

        if request.source_scope in {"provided_only", "local_private"}:
            return self._rule_result(
                False, f"source_scope_{request.source_scope}", request
            )

        if request.provided_context_sufficient:
            return self._rule_result(False, "provided_context_sufficient", request)

        if self._matches(_EXPLICIT_PUBLIC_LOOKUP_PATTERNS, request.task):
            return self._rule_result(True, "explicit_public_web_instruction", request)

        if (
            request.freshness in {"current", "recent"}
            and request.source_scope == "public"
        ):
            return self._rule_result(
                True, f"public_freshness_{request.freshness}", request
            )

        if request.source_scope == "public" and self._matches(
            _LIVE_PUBLIC_PATTERNS, request.task
        ):
            return self._rule_result(True, "public_live_fact", request)

        if self._matches(_LIVE_PUBLIC_PATTERNS, request.task):
            return self._rule_result(True, "live_public_fact", request)

        if self._matches(_VOLATILE_FACT_PATTERNS, request.task):
            return self._rule_result(True, "volatile_public_fact", request)

        if len(request.task) <= 600 and self._matches(
            _PROVIDED_ONLY_PATTERNS, request.task
        ):
            return self._rule_result(False, "bounded_transform_task", request)

        if self._matches(_LOCAL_FILE_PATTERNS, request.task):
            return self._rule_result(False, "local_file_or_repo", request)

        if self._matches(_CONNECTED_APP_PATTERNS, request.task):
            return self._rule_result(False, "connected_app_data", request)

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

    @staticmethod
    def _background_context(value: Any, max_chars: int = 1200) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value[-max_chars:]
        return value

    def decide(self, request: SearchGateRequest) -> dict[str, Any]:
        hard = self._hard_gate(request)
        if hard is not None:
            return hard

        state = {
            "task": request.task,
            "background_context": self._background_context(request.context),
            "freshness_requirement": request.freshness,
            "source_scope": request.source_scope,
            "provided_context_sufficient": request.provided_context_sufficient,
        }
        primitive = DecisionRequest(
            primitive="noul",
            state=state,
            instructions=(
                "Does the CURRENT USER TASK require PUBLIC INTERNET or WEB lookup for "
                "current/public facts? The background context is only for resolving short "
                "references such as 'this model', 'continue', or 'how is it going'; do not "
                "trigger web search merely because the background contains dates, current "
                "events, or words like today/latest. Answer false when the task can be "
                "completed from local files, connected apps, databases, supplied context, "
                "the existing conversation, or stable general knowledge. Needing a local "
                "tool or connector is not the same as needing public web search."
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