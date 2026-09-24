"""Run MLX on exactly the decision subset supported by a fixed-shape ANE result."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.quality.metrics import score_records


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def latency_summary(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--subset", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT
        / "datasets/typed-decisions/all/test-00000-of-00001.parquet",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from laya_mlx import Agent

    subset = json.loads(args.subset.read_text())
    supported = {
        (item["case_id"], item["question_name"])
        for item in subset["decisions"]
        if item["status"] == "supported"
    }

    rows = pq.read_table(args.dataset).to_pylist()
    started = time.perf_counter()
    agent = Agent(args.model, dtype="float16", batch_size=1)
    load_seconds = time.perf_counter() - started

    records: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    latencies: list[float] = []
    latency_by_workflow: dict[str, list[float]] = defaultdict(list)
    latency_by_type: dict[str, list[float]] = defaultdict(list)

    started_run = time.perf_counter()
    completed = 0

    for row in rows:
        state = json.loads(row["state"])
        questions = json.loads(row["questions"])
        gold = json.loads(row["gold"])
        for qid, question in questions.items():
            key = (row["id"], qid)
            if key not in supported:
                continue

            completed += 1
            call_started = time.perf_counter()
            response = agent.predict(state, {qid: question})
            latency_ms = (time.perf_counter() - call_started) * 1000.0
            answer = response["answers"][qid]

            latencies.append(latency_ms)
            latency_by_workflow[row["workflow"]].append(latency_ms)
            latency_by_type[question["type"]].append(latency_ms)

            decisions.append(
                {
                    "case_id": row["id"],
                    "workflow": row["workflow"],
                    "question_name": qid,
                    "question_type": question["type"],
                    "latency_ms": latency_ms,
                    "answer": answer,
                }
            )
            records.append(
                {
                    "case_id": row["id"],
                    "workflow": row["workflow"],
                    "question_name": qid,
                    "question_type": question["type"],
                    "question": question,
                    "gold": gold[qid],
                    "answer": answer,
                    "status": "ok",
                }
            )

            if completed % 100 == 0:
                print(f"MLX subset: {completed}/{len(supported)} decisions", flush=True)

    metrics = score_records(records)
    payload = {
        "model": str(args.model),
        "dtype": "float16",
        "batch_size": 1,
        "subset_source": str(args.subset),
        "supported_decisions": len(supported),
        "load_seconds": load_seconds,
        "elapsed_seconds": time.perf_counter() - started_run,
        "metrics": metrics,
        "latency": {
            "all": latency_summary(latencies),
            "by_workflow": {
                key: latency_summary(value)
                for key, value in sorted(latency_by_workflow.items())
            },
            "by_question_type": {
                key: latency_summary(value)
                for key, value in sorted(latency_by_type.items())
            },
        },
        "decisions": decisions,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    print(
        f"FINAL MLX subset: decisions={len(supported)}, "
        f"accuracy={metrics['accuracy']}, "
        f"p50={payload['latency']['all']['p50_ms']} ms",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
