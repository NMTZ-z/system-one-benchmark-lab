"""Evaluate a practical MLX + fixed-L512 ANE token-length router."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psutil
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.quality.compare_backends import selected_label
from benchmarks.quality.metrics import score_records
from benchmarks.quality.run_typed_decisions import DATASET_REVISION, save_atomic


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


def stats(values: list[float]) -> dict[str, float | int]:
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


def answer_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    probability = 0.0
    score = 0.0
    noul = 0.0
    confidence = abs(
        float(left.get("confidence", 0.0)) - float(right.get("confidence", 0.0))
    )
    action = 0.0

    if left["type"] in ("choice", "score"):
        for key, value in left["probabilities"].items():
            probability = max(
                probability,
                abs(float(value) - float(right["probabilities"][key])),
            )
    if left["type"] == "score":
        score = abs(float(left["score"]) - float(right["score"]))
    if left["type"] == "noul":
        noul = abs(float(left["noul"]) - float(right["noul"]))

    left_action = left.get("action", {}).get("act_probability")
    right_action = right.get("action", {}).get("act_probability")
    if left_action is not None and right_action is not None:
        action = abs(float(left_action) - float(right_action))

    return {
        "probability": probability,
        "score": score,
        "noul": noul,
        "confidence": confidence,
        "action_probability": action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ane-package", type=Path, required=True)
    parser.add_argument("--ane-length", type=int, default=512)
    parser.add_argument("--ane-min-tokens", type=int, default=192)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT
        / "datasets/typed-decisions/all/test-00000-of-00001.parquet",
    )
    parser.add_argument("--reference-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--save-every", type=int, default=20)
    args = parser.parse_args()

    from laya_coreml.ane import ANEAgent
    from laya_mlx import Agent as MLXAgent

    process = psutil.Process(os.getpid())
    rss_before = process.memory_info().rss

    started = time.perf_counter()
    mlx = MLXAgent(args.source, dtype="float16", batch_size=1)
    mlx_load_seconds = time.perf_counter() - started
    rss_after_mlx = process.memory_info().rss

    started = time.perf_counter()
    ane = ANEAgent(
        args.source,
        package=args.ane_package,
        length=args.ane_length,
        compute_units="cpu_ne",
    )
    ane_load_seconds = time.perf_counter() - started
    rss_after_both = process.memory_info().rss

    reference = json.loads(args.reference_run.read_text())
    reference_answers = {
        (item["case_id"], item["question_name"]): item["answer"]
        for item in reference["decisions"]
    }

    rows = pq.read_table(args.dataset).to_pylist()
    decisions: list[dict[str, Any]] = []
    score_inputs: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    total_latencies: list[float] = []
    route_latencies: list[float] = []
    backend_latencies: dict[str, list[float]] = defaultdict(list)
    total_by_route: dict[str, list[float]] = defaultdict(list)
    total_by_workflow: dict[str, list[float]] = defaultdict(list)
    total_by_type: dict[str, list[float]] = defaultdict(list)

    mismatches: list[dict[str, Any]] = []
    max_delta = {
        "probability": 0.0,
        "score": 0.0,
        "noul": 0.0,
        "confidence": 0.0,
        "action_probability": 0.0,
    }

    started_run = time.perf_counter()
    processed_since_save = 0

    payload: dict[str, Any] = {
        "dataset": {
            "repo": "LocalLLaMA/typed-decisions",
            "revision": DATASET_REVISION,
            "split": "all/test",
            "cases": len(rows),
            "decisions": sum(int(row["n_questions"]) for row in rows),
        },
        "router": {
            "policy": (
                f"mlx if tokens < {args.ane_min_tokens}; "
                f"ane_l{args.ane_length} if {args.ane_min_tokens} <= tokens <= "
                f"{args.ane_length}; mlx if tokens > {args.ane_length}"
            ),
            "ane_min_tokens": args.ane_min_tokens,
            "ane_max_tokens": args.ane_length,
            "routing_length_source": "ANE tokenizer/prompt prepare on raw state + one question",
        },
        "models": {
            "mlx": {"source": str(args.source), "dtype": "float16", "batch_size": 1},
            "ane": {
                "source": str(args.source),
                "package": str(args.ane_package),
                "length": args.ane_length,
                "compute_units": "cpu_ne",
                "manifest": ane.manifest,
            },
        },
        "load": {
            "rss_before_bytes": rss_before,
            "mlx_load_seconds": mlx_load_seconds,
            "rss_after_mlx_bytes": rss_after_mlx,
            "ane_load_seconds": ane_load_seconds,
            "rss_after_both_bytes": rss_after_both,
        },
        "reference_run": str(args.reference_run),
        "measurement": (
            "one raw-state decision at a time; total latency includes routing tokenization "
            "plus the chosen backend's complete predict call; both backends resident"
        ),
        "decisions": decisions,
    }

    for row in rows:
        state = json.loads(row["state"])
        questions = json.loads(row["questions"])
        gold = json.loads(row["gold"])

        for name, question in questions.items():
            total_started = time.perf_counter()
            route_started = total_started
            items, _ = ane.prepare(state, {name: question})
            tokens = len(items[0]["ids"])
            options = len(items[0]["markers"])
            route_ms = (time.perf_counter() - route_started) * 1000.0

            if tokens < args.ane_min_tokens:
                route = "mlx_short"
                backend = mlx
            elif tokens <= args.ane_length and options <= 32:
                route = "ane"
                backend = ane
            else:
                route = "mlx_long"
                backend = mlx

            inference_started = time.perf_counter()
            response = backend.predict(state, {name: question})
            backend_ms = (time.perf_counter() - inference_started) * 1000.0
            total_ms = (time.perf_counter() - total_started) * 1000.0
            answer = response["answers"][name]

            route_counts[route] += 1
            route_latencies.append(route_ms)
            backend_latencies[route].append(backend_ms)
            total_by_route[route].append(total_ms)
            total_by_workflow[row["workflow"]].append(total_ms)
            total_by_type[question["type"]].append(total_ms)
            total_latencies.append(total_ms)

            reference_answer = reference_answers[(row["id"], name)]
            left_selected = selected_label(answer)
            right_selected = selected_label(reference_answer)
            if left_selected != right_selected:
                mismatches.append(
                    {
                        "case_id": row["id"],
                        "question": name,
                        "workflow": row["workflow"],
                        "type": question["type"],
                        "tokens": tokens,
                        "route": route,
                        "router_selected": left_selected,
                        "reference_selected": right_selected,
                    }
                )

            delta = answer_delta(answer, reference_answer)
            for key, value in delta.items():
                max_delta[key] = max(max_delta[key], value)

            decision = {
                "case_id": row["id"],
                "workflow": row["workflow"],
                "question_name": name,
                "question_type": question["type"],
                "tokens": tokens,
                "options": options,
                "route": route,
                "route_ms": route_ms,
                "backend_ms": backend_ms,
                "total_ms": total_ms,
                "answer": answer,
            }
            decisions.append(decision)
            score_inputs.append(
                {
                    "case_id": row["id"],
                    "workflow": row["workflow"],
                    "question_name": name,
                    "question_type": question["type"],
                    "question": question,
                    "gold": gold[name],
                    "answer": answer,
                    "status": "ok",
                }
            )

            processed_since_save += 1
            if processed_since_save >= args.save_every:
                payload["progress"] = {
                    "completed": len(decisions),
                    "route_counts": dict(sorted(route_counts.items())),
                }
                save_atomic(args.output, payload)
                processed_since_save = 0

            if len(decisions) % 100 == 0:
                print(
                    f"router: {len(decisions)}/2000 "
                    f"routes={dict(sorted(route_counts.items()))}",
                    flush=True,
                )

    metrics = score_records(score_inputs)
    payload.update(
        elapsed_seconds=time.perf_counter() - started_run,
        route_counts=dict(sorted(route_counts.items())),
        metrics=metrics,
        parity_vs_mlx={
            "decisions": len(decisions),
            "selected_mismatches": len(mismatches),
            "selected_agreements": len(decisions) - len(mismatches),
            "selected_agreement_rate": (len(decisions) - len(mismatches))
            / len(decisions),
            "mismatch_examples": mismatches[:50],
            "max_probability_abs_delta": max_delta["probability"],
            "max_score_abs_delta": max_delta["score"],
            "max_noul_abs_delta": max_delta["noul"],
            "max_confidence_abs_delta": max_delta["confidence"],
            "max_action_probability_abs_delta": max_delta["action_probability"],
        },
        latency={
            "total": stats(total_latencies),
            "routing": stats(route_latencies),
            "backend_by_route": {
                key: stats(value) for key, value in sorted(backend_latencies.items())
            },
            "total_by_route": {
                key: stats(value) for key, value in sorted(total_by_route.items())
            },
            "total_by_workflow": {
                key: stats(value) for key, value in sorted(total_by_workflow.items())
            },
            "total_by_question_type": {
                key: stats(value) for key, value in sorted(total_by_type.items())
            },
        },
        rss_after_run_bytes=process.memory_info().rss,
    )
    payload.pop("progress", None)
    save_atomic(args.output, payload)

    print(
        f"FINAL router: routes={payload['route_counts']} "
        f"accuracy={metrics['accuracy']} "
        f"mismatches={len(mismatches)} "
        f"p50={payload['latency']['total']['p50_ms']:.3f} ms",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
