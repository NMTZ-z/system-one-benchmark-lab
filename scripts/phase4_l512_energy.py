#!/usr/bin/env python3
"""Balanced PSTR energy comparison for 421M MLX vs fixed L512 ANE."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from laya_coreml.ane import ANEAgent
from laya_mlx import Agent as MLXAgent

from benchmarks.energy import Sampler, comparison, endpoint_block, idle, summarize_power


def percentile(values: list[int], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return float(ordered[lo] * (1 - weight) + ordered[hi] * weight)


def selected_label(answer: dict) -> str:
    if answer["type"] == "choice":
        return str(answer["choice"])
    if answer["type"] == "noul":
        return "true" if float(answer["noul"]) >= 0.5 else "false"
    probabilities = answer["probabilities"]
    return str(max(probabilities, key=probabilities.get))


def choose_representative(decisions: list[dict], count: int) -> list[dict]:
    supported = sorted(
        (item for item in decisions if item["status"] == "supported"),
        key=lambda item: (item["token_length"], item["case_id"], item["question_name"]),
    )
    if count >= len(supported):
        return supported
    indices = np.linspace(0, len(supported) - 1, num=count)
    chosen = []
    used = set()
    for raw in indices:
        index = round(float(raw))
        while index in used and index + 1 < len(supported):
            index += 1
        used.add(index)
        chosen.append(supported[index])
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--subset", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sampler", type=Path, required=True)
    parser.add_argument("--representative-decisions", type=int, default=128)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--idle-seconds", type=float, default=10.0)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--sample-ms", type=int, default=500)
    parser.add_argument("--max-system-watts", type=float, default=500.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.seconds < 10 or args.idle_seconds < 6 or args.cycles < 1:
        parser.error("Require seconds>=10, idle-seconds>=6, cycles>=1")

    subset = json.loads(args.subset.read_text())
    selected = choose_representative(subset["decisions"], args.representative_decisions)

    rows = pq.read_table(args.dataset).to_pylist()
    by_id = {row["id"]: row for row in rows}
    cases = []
    metadata = []
    for item in selected:
        row = by_id[item["case_id"]]
        questions = json.loads(row["questions"])
        state = json.loads(row["state"])
        cases.append((state, {item["question_name"]: questions[item["question_name"]]}))
        metadata.append(
            {
                "case_id": item["case_id"],
                "question_name": item["question_name"],
                "workflow": item["workflow"],
                "question_type": item["question_type"],
                "token_length": item["token_length"],
            }
        )

    agents = {
        "mlx": MLXAgent(
            args.source,
            dtype="float16",
            batch_size=1,
            compile=True,
            cache_prompts=True,
            pad_to_multiple=32,
        ),
        "ane": ANEAgent(
            args.source,
            package=args.package,
            length=512,
            compute_units="cpu_ne",
        ),
    }

    warmup = {}
    for backend, agent in agents.items():
        results = []
        latencies = []
        # One pass across the representative set gives both compilation warmup
        # and per-prompt expected outputs for the stability checks.
        for case in cases:
            started = time.perf_counter()
            result = agent.predict(*case)
            latencies.append((time.perf_counter() - started) * 1000.0)
            results.append(result)
        warmup[backend] = {"latency_ms": latencies, "results": results}

    cross_selected_agreement = []
    for mlx_result, ane_result in zip(
        warmup["mlx"]["results"], warmup["ane"]["results"]
    ):
        key = next(iter(mlx_result["answers"]))
        cross_selected_agreement.append(
            selected_label(mlx_result["answers"][key])
            == selected_label(ane_result["answers"][key])
        )

    token_lengths = [item["token_length"] for item in metadata]
    report = {
        "schema_version": 1,
        "measurement": {
            "scope": (
                "balanced saturated complete-predict blocks over a deterministic "
                "length-stratified sample of real Typed Decisions inputs; both models "
                "resident; load and warmup excluded"
            ),
            "system_power": (
                "SMC PSTR only; includes baseline machine power; "
                "not a calibrated external meter"
            ),
            "integration": (
                "trapezoidal over monotonic receive timestamps with interpolated "
                "interval boundaries"
            ),
        },
        "settings": {
            "representative_decisions": len(cases),
            "seconds": args.seconds,
            "idle_seconds": args.idle_seconds,
            "cycles": args.cycles,
            "sample_ms": args.sample_ms,
            "max_system_watts": args.max_system_watts,
            "block_order": ["mlx", "ane", "ane", "mlx"],
        },
        "workload": {
            "selection": "evenly spaced over the 1966 naturally fitting L512 decisions sorted by token length",
            "token_length": {
                "min": min(token_lengths),
                "p25": percentile(token_lengths, 0.25),
                "p50": percentile(token_lengths, 0.50),
                "p75": percentile(token_lengths, 0.75),
                "p95": percentile(token_lengths, 0.95),
                "max": max(token_lengths),
                "mean": statistics.fmean(token_lengths),
            },
            "by_workflow": {
                key: sum(item["workflow"] == key for item in metadata)
                for key in sorted({item["workflow"] for item in metadata})
            },
            "by_question_type": {
                key: sum(item["question_type"] == key for item in metadata)
                for key in sorted({item["question_type"] for item in metadata})
            },
            "items": metadata,
        },
        "models": {
            "mlx": {"source": str(args.source), "batch_size": 1, "dtype": "float16"},
            "ane": {
                "source": str(args.source),
                "package": str(args.package),
                "length": 512,
                "compute_units": "cpu_ne",
                "manifest": agents["ane"].manifest,
            },
        },
        "sampler": {
            "path": str(args.sampler),
            "sha256": hashlib.sha256(args.sampler.read_bytes()).hexdigest(),
        },
        "warmup": {
            backend: {
                "calls": len(value["latency_ms"]),
                "latency_ms": value["latency_ms"],
            }
            for backend, value in warmup.items()
        },
        "cross_backend_selected_agreement": {
            "agreements": sum(cross_selected_agreement),
            "decisions": len(cross_selected_agreement),
        },
        "blocks": [],
    }

    order = ("mlx", "ane", "ane", "mlx")
    sampler = Sampler(args.sampler, args.sample_ms, args.max_system_watts).start()
    try:
        before = idle(sampler, args.idle_seconds)
        for cycle in range(args.cycles):
            for backend in order:
                block = endpoint_block(
                    agents[backend],
                    cases,
                    args.seconds,
                    rate=0,
                    expected=warmup[backend]["results"],
                )
                block.update(backend=backend, cycle=cycle, idle_before=before)
                block["power"] = summarize_power(sampler, block["start"], block["end"])
                after = idle(sampler, args.idle_seconds)
                block["idle_after"] = after
                idle_watts = (
                    before["power"]["sys_power"]["mean_watts"]
                    + after["power"]["sys_power"]["mean_watts"]
                ) / 2.0
                block["idle_mean_watts"] = idle_watts
                block["incremental_system_joules"] = (
                    block["power"]["sys_power"]["joules"]
                    - idle_watts * block["duration_seconds"]
                )
                report["blocks"].append(block)
                report["summary"] = comparison(report["blocks"])
                report["power_samples"] = sampler.samples.copy()
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
                print(
                    f"cycle={cycle} {backend}: "
                    f"P50={block['latency']['p50_ms']:.2f} ms "
                    f"sys={block['power']['sys_power']['mean_watts']:.2f} W "
                    f"calls={block['completed_decisions']} "
                    f"unstable={block['unstable_rounded_results']}",
                    flush=True,
                )
                before = after
    finally:
        sampler.stop()
        report["power_samples"] = sampler.samples.copy()
        report["sampler_errors"] = sampler.errors
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps(report["summary"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
