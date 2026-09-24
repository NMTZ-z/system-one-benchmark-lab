"""Fixed-shape Apple Neural Engine runtime adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_reference_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    reference = project_root / "references" / "laya-coreml"
    if reference.exists() and str(reference) not in sys.path:
        sys.path.insert(0, str(reference))


class ANERuntime:
    name = "ane_l512"

    def __init__(self, source: str | Path, package: str | Path, *, length: int = 512):
        _ensure_reference_path()
        from laya_coreml.ane import ANEAgent

        self.source = Path(source)
        self.package = Path(package)
        self.length = length
        self.agent = ANEAgent(
            self.source,
            package=self.package,
            length=length,
            compute_units="cpu_ne",
        )

    def token_count(self, state: Any, question: dict[str, Any]) -> int:
        items, _ = self.agent.prepare(state, {"decision": question})
        return len(items[0]["ids"])

    def predict(self, state: Any, question: dict[str, Any]) -> dict[str, Any]:
        response = self.agent.predict(state, {"decision": question})
        return response["answers"]["decision"]
