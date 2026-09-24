"""Runtime protocol."""

from __future__ import annotations

from typing import Any, Protocol


class DecisionRuntime(Protocol):
    name: str

    def predict(self, state: Any, question: dict[str, Any]) -> dict[str, Any]:
        """Return one Laya-compatible answer."""

    def token_count(self, state: Any, question: dict[str, Any]) -> int:
        """Return the prepared token length for one question."""
