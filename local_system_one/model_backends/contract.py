"""Strict model-neutral Typed Decision contract. Never exposed on production HTTP wire."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Primitive = Literal["choice", "score", "noul"]
PROTOCOL_VERSION = "model-backend-pilot-v1"
PROBABILITY_TOLERANCE = 1e-3
SCORE_TOLERANCE = 0.011  # Supports a score rounded to two decimals.
MAX_SERIALIZED_REQUEST_BYTES = 32768


class ModelContractError(ValueError):
    """Request or provider result violates the research contract."""


class UnsupportedCapability(ModelContractError):
    """A provider cannot safely represent the requested task."""


def finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelContractError(f"{field_name} must be numeric, not boolean")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ModelContractError(f"{field_name} must be representable") from exc
    if not math.isfinite(result):
        raise ModelContractError(f"{field_name} must be finite")
    return result


def probability(value: Any, name: str) -> float:
    value = finite_number(value, name)
    if not 0 <= value <= 1:
        raise ModelContractError(f"{name} must be in [0,1]")
    return value


def validate_json(value: Any, *, depth: int = 0) -> None:
    if depth > 32:
        raise ModelContractError("research JSON nesting exceeds 32")
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)):
        finite_number(value, "JSON number")
    elif isinstance(value, list):
        for item in value:
            validate_json(item, depth=depth + 1)
    elif isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ModelContractError("JSON keys must be strings")
        for item in value.values():
            validate_json(item, depth=depth + 1)
    else:
        raise ModelContractError(f"invalid JSON type: {type(value).__name__}")


@dataclass(frozen=True)
class TypedRequest:
    primitive: Primitive
    state: Any
    instructions: str
    criteria: Any = None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.primitive not in ("choice", "score", "noul"):
            raise UnsupportedCapability(f"unsupported primitive: {self.primitive}")
        if not isinstance(self.state, (str, dict, list)):
            raise ModelContractError("state must be a string, object or array")
        if not isinstance(self.instructions, str) or not self.instructions.strip():
            raise ModelContractError("instructions must be non-empty")
        if self.request_id is not None and (
            not isinstance(self.request_id, str) or not self.request_id or len(self.request_id) > 128
        ):
            raise ModelContractError("request_id must be non-empty and <=128 chars")
        if self.primitive == "choice":
            if not 2 <= len(self.options) <= 255:
                raise ModelContractError("choice must have 2-255 labels")
        elif self.primitive == "score":
            if not isinstance(self.criteria, list) or not 2 <= len(self.criteria) <= 10:
                raise ModelContractError("score must have 2-10 levels")
            if any(not isinstance(x, str) or not x.strip() for x in self.criteria):
                raise UnsupportedCapability("research score levels must be non-empty strings")
        elif self.criteria is not None:
            if not isinstance(self.criteria, dict) or set(self.criteria) - {"true", "false"}:
                raise ModelContractError("noul criteria may only define true/false")
        validate_json(self.state)
        validate_json(self.criteria)
        nbytes = len(json.dumps(self.state, ensure_ascii=False).encode("utf-8"))
        nbytes += len(json.dumps(self.to_question(), ensure_ascii=False).encode("utf-8"))
        if nbytes > MAX_SERIALIZED_REQUEST_BYTES:
            raise ModelContractError("research request content exceeds 32KiB")

    @property
    def options(self) -> tuple[str, ...]:
        if self.primitive != "choice":
            return ()
        if isinstance(self.criteria, dict):
            values = list(self.criteria)
        elif isinstance(self.criteria, list):
            values = self.criteria
        else:
            raise ModelContractError("choice criteria must be list or map")
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ModelContractError("choice labels must be non-empty strings")
        if len(set(values)) != len(values):
            raise ModelContractError("duplicate choice labels")
        return tuple(values)

    def to_question(self) -> dict[str, Any]:
        result = {"type": self.primitive, "instructions": self.instructions}
        if self.primitive == "choice":
            result["criteria"] = (
                dict(self.criteria) if isinstance(self.criteria, dict)
                else {key: None for key in self.options}
            )
        elif self.criteria is not None:
            result["criteria"] = self.criteria
        return result


@dataclass(frozen=True)
class ModelCapabilities:
    primitives: frozenset[str]
    remote: bool
    probabilities: bool
    usage: bool


@dataclass(frozen=True)
class TypedResult:
    primitive: Primitive
    decision: str | float | bool
    probabilities: dict[str, float]
    provider_id: str
    model_requested: str
    model_resolved: str
    execution_backend: str
    request_id: str | None
    latency_ms: float
    usage: dict[str, int] | None = None
    provider_confidence: float | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    def validate_against(self, req: TypedRequest) -> "TypedResult":
        if self.primitive != req.primitive or self.request_id != req.request_id:
            raise ModelContractError("primitive/request_id mismatch")
        for name in ("provider_id", "model_requested", "model_resolved", "execution_backend"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ModelContractError(f"{name} missing")
        if self.execution_backend not in {"mlx", "ane", "remote_http"}:
            raise ModelContractError("invalid execution_backend")
        if finite_number(self.latency_ms, "latency_ms") < 0:
            raise ModelContractError("negative latency")
        if self.provider_confidence is not None:
            probability(self.provider_confidence, "provider_confidence")
        if self.usage is not None:
            if not isinstance(self.usage, dict) or set(self.usage) != {"input_tokens", "output_tokens"}:
                raise ModelContractError("usage must include input/output tokens")
            if any(type(x) is not int or not 0 <= x <= 2**53 - 1 for x in self.usage.values()):
                raise ModelContractError("invalid token usage")
        if not isinstance(self.probabilities, dict):
            raise ModelContractError("probabilities must be a map")
        expected = (
            set(req.options) if req.primitive == "choice" else
            {str(i) for i in range(len(req.criteria))} if req.primitive == "score" else
            {"true", "false"}
        )
        if set(self.probabilities) != expected:
            raise ModelContractError("probability labels mismatch")
        probs = {key: probability(v, f"probability.{key}") for key, v in self.probabilities.items()}
        if abs(sum(probs.values()) - 1) > PROBABILITY_TOLERANCE:
            raise ModelContractError("invalid probability total")
        if req.primitive == "choice":
            if not isinstance(self.decision, str) or self.decision not in expected:
                raise ModelContractError("choice not among labels")
            if not math.isclose(probs[self.decision], max(probs.values()), abs_tol=1e-8):
                raise ModelContractError("choice not at probability maximum")
            # Ties are valid, but not arbitrarily resolved here.
        elif req.primitive == "score":
            score = finite_number(self.decision, "score")
            weighted = sum(int(k) * v for k, v in probs.items())
            if not 0 <= score <= len(expected) - 1 or abs(score - weighted) > SCORE_TOLERANCE:
                raise ModelContractError("score inconsistent with weighted level")
        else:
            if type(self.decision) is not bool or self.decision != (probs["true"] >= 0.5):
                raise ModelContractError("noul boolean inconsistent with probability")
        return self

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "primitive": self.primitive, "decision": self.decision,
            "probabilities": self.probabilities, "provider_id": self.provider_id,
            "model_requested": self.model_requested, "model_resolved": self.model_resolved,
            "execution_backend": self.execution_backend, "request_id": self.request_id,
            "latency_ms": self.latency_ms,
        }
        if self.usage is not None:
            result["usage"] = dict(self.usage)
        if self.provider_confidence is not None:
            result["provider_confidence"] = self.provider_confidence
        if self.extensions:
            result["extensions"] = dict(self.extensions)
        return result


class DecisionModelProvider(Protocol):
    provider_id: str
    capabilities: ModelCapabilities

    def evaluate(self, request: TypedRequest) -> TypedResult:
        """Return a validated model-neutral result, not a Laya wire response."""
