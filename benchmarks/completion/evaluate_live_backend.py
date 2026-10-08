#!/usr/bin/env python3
"""Evaluate Completion Gate with a live Local System One choice backend.

This runner is useful when an already-running pre-Phase-8A service exposes the
generic /v1/choice primitive but not the new Completion endpoint. Completion
rules and safety thresholds execute from the current checkout; only model choice
inference is delegated to the live service.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.completion.evaluate import LABELS, metrics, post_json, public_path
from local_system_one.health import ANEHealthGate
from local_system_one.metrics import ServiceMetrics
from local_system_one.workflows.completion_gate import (
    CompletionGate,
    CompletionGateRequest,
)


class RemoteChoiceEngine:
    def __init__(self, url: str, timeout: float, backend: str):
        self.url = url
        self.timeout = timeout
        self.backend = backend
        self.metrics = ServiceMetrics()
        self.health = ANEHealthGate(available=False)

    def decide(self, request):
        return post_json(
            self.url,
            {
                "state": request.state,
                "instructions": request.instructions,
                "criteria": request.criteria,
                "request_id": request.request_id,
                "backend": self.backend,
            },
            self.timeout,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=Path(__file__).with_name("gold_v0.1.jsonl"))
    parser.add_argument("--choice-url", default="http://127.0.0.1:8787/v1/choice")
    parser.add_argument("--backend", choices=("auto", "mlx", "ane"), default="ane")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = [json.loads(line) for line in args.gold.read_text().splitlines() if line.strip()]
    engine = RemoteChoiceEngine(args.choice_url, args.timeout, args.backend)
    gate = CompletionGate(engine)
    predictions: list[dict[str, Any]] = []
    started = time.perf_counter()

    for item in cases:
        request = CompletionGateRequest.from_payload(
            {
                "task": item["task"],
                "current_result": item["current_result"],
                "execution_state": item["execution_state"],
                "request_id": item["id"],
            }
        )
        result = gate.decide(request)
        prediction = result["decision"]
        if prediction not in LABELS:
            raise ValueError(f"invalid prediction: {prediction}")
        predictions.append(
            {
                "id": item["id"],
                "source": item["source"],
                "label": item["label"],
                "prediction": prediction,
                "decision_source": result.get("decision_source"),
                "reason": result.get("reason"),
                "backend": result.get("backend"),
                "latency_ms": result.get("latency_ms"),
                "confidence": result.get("confidence"),
            }
        )

    by_source = {
        source: metrics([row for row in predictions if row["source"] == source])
        for source in ("real", "synthetic")
    }
    report = {
        "benchmark": "completion-gate-v0.1",
        "runner": "current CompletionGate + live generic choice backend",
        "choice_endpoint": args.choice_url,
        "backend_override": args.backend,
        "gold_file": public_path(args.gold),
        "cases_total": len(cases),
        "source_counts": dict(Counter(row["source"] for row in cases)),
        "label_counts_by_source": {
            source: dict(Counter(row["label"] for row in cases if row["source"] == source))
            for source in ("real", "synthetic")
        },
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
        "metrics_by_source": by_source,
        "predictions": predictions,
        "privacy": "no task/current_result bodies persisted in benchmark output",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"metrics_by_source": by_source, "cases_total": len(cases)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
