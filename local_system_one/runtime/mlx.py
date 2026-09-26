"""MLX runtime adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .sources import normalize_source


class MLXRuntime:
    name = "mlx"

    def __init__(self, source: str | Path):
        from laya_mlx import Agent

        model_source, revision = normalize_source(source)
        if isinstance(model_source, Path) and not model_source.is_dir():
            raise FileNotFoundError(f"model source directory not found: {model_source}")
        self.agent = Agent(
            model_source,
            revision=revision,
            dtype="float16",
            batch_size=1,
            compile=True,
            cache_prompts=True,
            pad_to_multiple=32,
        )
        self.source = Path(self.agent.model_dir)

    def token_count(self, state: Any, question: dict[str, Any]) -> int:
        items, _ = self.agent.prepare(state, {"decision": question})
        return len(items[0]["ids"])

    def predict(self, state: Any, question: dict[str, Any]) -> dict[str, Any]:
        response = self.agent.predict(state, {"decision": question})
        return response["answers"]["decision"]