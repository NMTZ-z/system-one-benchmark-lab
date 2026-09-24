"""Validated request/response helpers for Local System One."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Primitive = Literal["choice", "score", "noul"]
BackendOverride = Literal["auto", "mlx", "ane"]


@dataclass(frozen=True)
class DecisionRequest:
    primitive: Primitive
    state: Any
    instructions: str
    criteria: Any = None
    request_id: str | None = None
    backend: BackendOverride = "auto"

    @classmethod
    def from_payload(cls, primitive: str, payload: dict[str, Any]) -> DecisionRequest:
        if primitive not in {"choice", "score", "noul"}:
            raise ValueError(f"unsupported primitive: {primitive}")
        if not isinstance(payload, dict):
            raise TypeError("request body must be a JSON object")
        if "state" not in payload:
            raise ValueError("state is required")

        instructions = payload.get("instructions")
        if primitive == "noul" and not instructions:
            instructions = payload.get("proposition")
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError("instructions must be a non-empty string")

        backend = payload.get("backend", "auto")
        if backend not in {"auto", "mlx", "ane"}:
            raise ValueError("backend must be auto, mlx, or ane")

        request_id = payload.get("request_id")
        if request_id is not None and not isinstance(request_id, str):
            raise ValueError("request_id must be a string when provided")

        criteria = payload.get("criteria", payload.get("options"))
        if primitive == "choice":
            if not isinstance(criteria, (list, dict)) or not criteria:
                raise ValueError("choice requires non-empty criteria/options")
        elif primitive == "score":
            if not isinstance(criteria, list) or not criteria:
                raise ValueError("score requires a non-empty criteria list")
        elif criteria is not None and not isinstance(criteria, dict):
            raise ValueError("noul criteria must be a dictionary when provided")

        return cls(
            primitive=primitive,
            state=payload["state"],
            instructions=instructions.strip(),
            criteria=criteria,
            request_id=request_id,
            backend=backend,
        )

    def question(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.primitive,
            "instructions": self.instructions,
        }
        if self.criteria is not None:
            result["criteria"] = self.criteria
        return result


def selected_label(answer: dict[str, Any]) -> str:
    kind = answer["type"]
    if kind == "choice":
        return str(answer["choice"])
    if kind == "noul":
        return "true" if float(answer["noul"]) >= 0.5 else "false"
    probabilities = answer["probabilities"]
    return str(max(probabilities, key=probabilities.get))


def normalized_answer(answer: dict[str, Any]) -> dict[str, Any]:
    kind = answer["type"]
    confidence = float(answer.get("confidence", 0.0))
    action_probability = answer.get("action", {}).get("act_probability")

    if kind == "choice":
        probabilities = {str(k): float(v) for k, v in answer["probabilities"].items()}
        return {
            "decision": str(answer["choice"]),
            "selected": str(answer["choice"]),
            "probabilities": probabilities,
            "confidence": confidence,
            "action_probability": (
                float(action_probability) if action_probability is not None else None
            ),
        }

    if kind == "score":
        probabilities = {str(k): float(v) for k, v in answer["probabilities"].items()}
        return {
            "decision": float(answer["score"]),
            "selected": str(max(probabilities, key=probabilities.get)),
            "probabilities": probabilities,
            "confidence": confidence,
            "action_probability": (
                float(action_probability) if action_probability is not None else None
            ),
        }

    probability_true = float(answer["noul"])
    return {
        "decision": probability_true >= 0.5,
        "selected": "true" if probability_true >= 0.5 else "false",
        "probabilities": {
            "false": 1.0 - probability_true,
            "true": probability_true,
        },
        "confidence": confidence,
        "action_probability": (
            float(action_probability) if action_probability is not None else None
        ),
    }
