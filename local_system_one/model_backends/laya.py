"""Thin Laya wrapper and legacy Gate facade, restricted to offline research.

No production DecisionEngine, route, thresholds or HTTP schema are modified.
"""
from __future__ import annotations

from typing import Any

from ..health import ANEHealthGate
from ..metrics import ServiceMetrics, error_accounting_scope, record_error_once
from ..schemas import DecisionRequest
from .contract import (
    ModelCapabilities, ModelContractError, TypedRequest, TypedResult, finite_number,
)


class LayaProvider:
    provider_id = "laya"
    capabilities = ModelCapabilities(frozenset({"choice", "score", "noul"}), False, True, False)

    def __init__(self, engine: Any, *, model_identity: str):
        if not model_identity:
            raise ValueError("Laya model_identity must be pinned or explicitly named")
        self.engine = engine
        self.model_identity = model_identity

    def evaluate(self, request: TypedRequest) -> TypedResult:
        # Keep the ORIGINAL Laya criterion representation, including Retry lists.
        legacy = self.engine.decide(DecisionRequest(
            primitive=request.primitive, state=request.state,
            instructions=request.instructions, criteria=request.criteria,
            request_id=request.request_id,
        ))
        if request.primitive == "choice":
            decision: str | float | bool = legacy["decision"]
        elif request.primitive == "score":
            decision = legacy["decision"]
        else:
            decision = legacy["decision"]
        backend = legacy["backend"]
        if backend not in ("mlx", "ane"):
            raise ModelContractError("Laya execution backend must be mlx or ane")
        extensions: dict[str, Any] = {
            "legacy_route_reason": legacy["route_reason"],
            "legacy_token_count": legacy["token_count"],
            "legacy_gate_confidence": finite_number(legacy["confidence"], "confidence"),
        }
        # Action head is Laya-specific, not a universal confidence estimate.
        if legacy.get("action_probability") is not None:
            extensions["laya_action_probability"] = legacy["action_probability"]
        return TypedResult(
            primitive=request.primitive, decision=decision,
            probabilities=legacy["probabilities"], provider_id=self.provider_id,
            model_requested=self.model_identity, model_resolved=self.model_identity,
            execution_backend=backend, request_id=request.request_id,
            latency_ms=legacy["latency_ms"], extensions=extensions,
        ).validate_against(request)


class ResearchEngine:
    """Invoke a provider while exposing only the legacy minimum consumed by the Gates.

    No HTTP service uses this facade. Remote token_count=-1 means unavailable,
    not zero tokens. Canonical research results retain optional usage separately.
    """

    def __init__(self, provider: Any):
        self.provider = provider
        self.metrics = getattr(getattr(provider, "engine", None), "metrics", None) or ServiceMetrics()
        self.health = getattr(getattr(provider, "engine", None), "health", None) or ANEHealthGate(available=False)
        self.last_result: TypedResult | None = None
        self.last_error: str | None = None

    def decide(self, request: DecisionRequest) -> dict[str, Any]:
        self.last_result = None
        self.last_error = None
        with error_accounting_scope():
            try:
                typed = TypedRequest(
                    primitive=request.primitive, state=request.state,
                    instructions=request.instructions, criteria=request.criteria,
                    request_id=request.request_id,
                )
                result = self.provider.evaluate(typed).validate_against(typed)
                self.last_result = result
                # Gate code requires a confidence field for Choice. Do not fake
                # missing provider confidence; a missing confidence fails closed.
                confidence = result.provider_confidence
                if confidence is None:
                    confidence = result.extensions.get("legacy_gate_confidence")
                if confidence is None and typed.primitive == "choice":
                    raise ModelContractError("choice provider confidence unavailable for legacy Gate")
                if self.provider.provider_id != "laya":
                    self.metrics.record(
                        backend=result.execution_backend,
                        route_reason="research:" + self.provider.provider_id,
                        latency_ms=result.latency_ms,
                    )
                return {
                    "decision": result.decision,
                    "probabilities": dict(result.probabilities),
                    "confidence": confidence,
                    "backend": result.execution_backend,
                    "route_reason": result.extensions.get(
                        "legacy_route_reason", "research:" + self.provider.provider_id
                    ),
                    "token_count": result.extensions.get("legacy_token_count", -1),
                    "latency_ms": result.latency_ms,
                    "request_id": result.request_id,
                }
            except Exception as error:
                self.last_error = type(error).__name__
                record_error_once(self.metrics, error)
                raise


class RuleOnlyEngine:
    """Compatibility baseline: never calls a model (Completion falls back to continue)."""

    def __init__(self) -> None:
        self.health = ANEHealthGate(available=False)
        self.metrics = ServiceMetrics()
        self.last_result = None
        self.last_error = None

    def decide(self, request: DecisionRequest) -> dict[str, Any]:
        self.last_error = "rule_only_no_model"
        raise ModelContractError("rule-only baseline: no model inference")
