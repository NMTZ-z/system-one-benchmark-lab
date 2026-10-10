#!/usr/bin/env python3
"""Shadow-only Phase 8B replay: separately capture rule, raw model, and final labels.

Inputs are read for inference only. Written artifacts contain IDs, labels and
numeric metadata, never original tasks, current results or model prompts.
Do not use any output here as authority to stop an Agent.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.completion.evaluate import LABELS, metrics
from benchmarks.completion.evaluate_live_backend import RemoteChoiceEngine
from local_system_one.workflows.completion_gate import (
    CompletionGate,
    CompletionGateRequest,
)


class CapturingEngine(RemoteChoiceEngine):
    def __init__(self, url: str, timeout: float, backend: str):
        super().__init__(url=url, timeout=timeout, backend=backend)
        self.raw: dict | None = None

    def decide(self, request):
        result = super().decide(request)
        probabilities = result.get("probabilities", {})
        self.raw = {
            "decision": result.get("decision"),
            "probabilities": {key: probabilities.get(key) for key in LABELS},
            "confidence": result.get("confidence"),
            "backend": result.get("backend"),
            "route_reason": result.get("route_reason"),
            "token_count": result.get("token_count"),
            "latency_ms": result.get("latency_ms"),
        }
        return result


def safe_numeric(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def quantiles(values):
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
    ordered = sorted(values)
    def p(pct):
        ix = (len(ordered) - 1) * pct
        lower, upper = int(ix), min(len(ordered) - 1, int(ix) + 1)
        return ordered[lower] * (upper - ix) + ordered[upper] * (ix - lower)
    return {"count": len(values), "p50_ms": p(.50), "p95_ms": p(.95), "mean_ms": statistics.mean(values)}


def run(gold: Path, choice_url: str, backend: str, timeout: float, max_cases: int) -> dict:
    cases = [json.loads(line) for line in gold.read_text().splitlines() if line.strip()]
    if max_cases > 0:
        cases = cases[:max_cases]
    engine = CapturingEngine(choice_url, timeout, backend)
    gate = CompletionGate(engine)  # original 8A settings: 0.70, no tuning
    rows = []
    for item in cases:
        engine.raw = None
        request = CompletionGateRequest.from_payload({
            "task": item["task"],
            "current_result": item["current_result"],
            "execution_state": item["execution_state"],
            "request_id": item["id"],
        })
        start = time.perf_counter()
        result = gate.decide(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        raw = engine.raw
        rows.append({
            "id": item["id"],
            "source": item.get("source", "unclassified"),
            "label": item["label"],
            "prediction": result["decision"],
            "deterministic_rule": result["decision"] if result["decision_source"] == "rule" else None,
            "rule_reason": result["reason"] if result["decision_source"] == "rule" else None,
            "raw_model_decision": raw["decision"] if raw else None,
            "raw_probabilities": raw["probabilities"] if raw else None,
            "raw_confidence": safe_numeric(raw["confidence"]) if raw else None,
            "raw_backend": raw["backend"] if raw else None,
            "route_reason": raw["route_reason"] if raw else None,
            "raw_latency_ms": safe_numeric(raw["latency_ms"]) if raw else None,
            "raw_token_count": raw["token_count"] if raw else None,
            "final_reason": result["reason"],
            "final_decision": result["decision"],
            "complete_threshold": gate.min_complete_probability,
            "wall_ms": elapsed_ms,
        })

    source_metrics = {s: metrics([r for r in rows if r["source"] == s])
                      for s in sorted({r["source"] for r in rows})}
    model_rows = [r for r in rows if r["raw_model_decision"] is not None]
    raw_metrics = {s: metrics([dict(r, prediction=r["raw_model_decision"])
                               for r in model_rows if r["source"] == s])
                   for s in sorted({r["source"] for r in model_rows})}
    return {
        "runner": "phase8b-original-8a-replay",
        "backend_request": backend,
        "complete_threshold_unchanged": .70,
        "case_count": len(rows),
        "rule_counts": dict(Counter(r["rule_reason"] for r in rows if r["rule_reason"])),
        "raw_counts": dict(Counter(r["raw_model_decision"] for r in model_rows)),
        "final_counts": dict(Counter(r["final_decision"] for r in rows)),
        "final_metrics_by_source": source_metrics,
        "raw_model_only_metrics_by_source": raw_metrics,
        "wall_latency": quantiles([r["wall_ms"] for r in rows]),
        "model_only_wall_latency": quantiles([r["wall_ms"] for r in model_rows]),
        "model_backend_distribution": dict(Counter(str(r["raw_backend"]) for r in model_rows)),
        "rows": rows,
        "privacy": "only ids, labels, finite probabilities, decisions and timings; no task text",
        "warning": "Old 8A corpus is NOT independent of Phase 8B development",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=ROOT / "benchmarks/completion/gold_v0.1.jsonl")
    parser.add_argument("--choice-url", default="http://127.0.0.1:8787/v1/choice")
    parser.add_argument("--backend", choices=("ane", "mlx", "auto"), default="ane")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.gold, args.choice_url, args.backend, args.timeout, args.max_cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
