"""MLX runtime adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class MLXRuntime:
    name = "mlx"

    def __init__(self, source: str | Path):
        from laya_mlx import Agent

        self.source = Path(source)
        self.agent = Agent(
            self.source,
            dtype="float16",
            batch_size=1,
            compile=True,
            cache_prompts=True,
            pad_to_multiple=32,
        )

    def token_count(self, state: Any, question: dict[str, Any]) -> int:
        items, _ = self.agent.prepare(state, {"decision": question})
        return len(items[0]["ids"])

    def predict(self, state: Any, question: dict[str, Any]) -> dict[str, Any]:
        response = self.agent.predict(state, {"decision": question})
        return response["answers"]["decision"]
