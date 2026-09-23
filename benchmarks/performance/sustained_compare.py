#!/usr/bin/env python3
"""Balanced sustained comparison of compiled MLX and published ANE bundles."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = PROJECT_ROOT / "references" / "laya-coreml"
if str(UPSTREAM) not in sys.path:
    sys.path.insert(0, str(UPSTREAM))

import laya_coreml
from benchmarks.cases import workload
from benchmarks.common import environment
from laya_mlx import Agent as MLXAgent

from benchmarks.energy import endpoint_block


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return resolved.name


def aggregate(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for backend in sorted({block["backend"] for block in blocks}):
        group = [block for block in blocks if block["backend"] == backend]
        latencies = np.asarray(
            [value for block in group for value in block["latency_ms"]],
            dtype=np.float64,
        )
        calls = sum(block["completed_decisions"] for block in group)
        duration = sum(block["duration_seconds"] for block in group)
        summary[backend] = {
            "blocks": len(group),
            "completed_decisions": calls,
            "active_duration_seconds": duration,
            "mean_interval_ms_per_decision": duration * 1000.0 / calls,
            "latency_mean_ms": float(latencies.mean()),
            "latency_p50_ms": float(np.percentile(latencies, 50)),
            "latency_p95_ms": float(np.percentile(latencies, 95)),
            "latency_p99_ms": float(np.percentile(latencies, 99)),
            "latency_min_ms": float(latencies.min()),
            "latency_max_ms": float(latencies.max()),
            "decisions_per_second": calls / duration,
            "unstable_rounded_results": sum(
                block["unstable_rounded_results"] for block in group
            ),
        }
    if "mlx" in summary:
        baseline = summary["mlx"]["mean_interval_ms_per_decision"]
        summary["speedup_vs_mlx"] = {
            backend: baseline / values["mean_interval_ms_per_decision"]
            for backend, values in summary.items()
            if backend not in {"mlx", "speedup_vs_mlx"}
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--fp16", type=Path, required=True)
    parser.add_argument("--w8", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--idle-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.seconds <= 0 or args.cycles < 1 or args.idle_seconds < 0:
        parser.error("seconds must be positive, cycles >= 1, idle-seconds >= 0")

    agents = {
        "mlx": MLXAgent(
            args.source,
            dtype="float16",
            batch_size=1,
            compile=True,
            cache_prompts=True,
            pad_to_multiple=32,
        ),
        "ane_fp16": laya_coreml.load(
            args.fp16,
            local_files_only=True,
            compute_units="cpu_ne",
        ),
        "ane_w8": laya_coreml.load(
            args.w8,
            local_files_only=True,
            compute_units="cpu_ne",
        ),
    }

    state, questions = workload(1)
    cases = []
    for suffix in range(8):
        changed = copy.deepcopy(state)
        changed["subject"] = f"Duplicate charge on invoice #441{suffix}"
        cases.append((changed, questions))

    warmup: dict[str, Any] = {}
    for backend, agent in agents.items():
        lengths = [len(agent.prepare(*case)[0][0]["ids"]) for case in cases]
        results, latencies = [], []
        for index in range(32):
            start = time.perf_counter()
            result = agent.predict(*cases[index % len(cases)])
            latencies.append((time.perf_counter() - start) * 1000.0)
            if index < len(cases):
                results.append(result)
        warmup[backend] = {
            "lengths": lengths,
            "latency_ms": latencies,
            "results": results,
        }

    answer_agreement = {
        backend: [
            all(
                lhs["answers"][key]["choice"] == rhs["answers"][key]["choice"]
                for key in lhs["answers"]
            )
            for lhs, rhs in zip(warmup["mlx"]["results"], warmup[backend]["results"])
        ]
        for backend in ("ane_fp16", "ane_w8")
    }
    if not all(all(values) for values in answer_agreement.values()):
        raise ValueError("Selected answers differ on the sustained workload")

    order = ("mlx", "ane_fp16", "ane_w8", "ane_w8", "ane_fp16", "mlx")
    report: dict[str, Any] = {
        "schema_version": 1,
        "environment": environment(),
        "measurement": (
            "balanced saturated complete-predict blocks; all compared models resident; "
            "loading and warmup excluded; no power telemetry in this run"
        ),
        "settings": {
            "seconds": args.seconds,
            "cycles": args.cycles,
            "idle_seconds_between_blocks": args.idle_seconds,
            "block_order": order,
        },
        "baseline_options": {
            "dtype": "float16",
            "batch_size": 1,
            "compile": True,
            "cache_prompts": True,
            "pad_to_multiple": 32,
        },
        "models": {
            "source": portable_path(args.source),
            "ane_fp16": {
                "path": portable_path(args.fp16),
                "manifest": agents["ane_fp16"].manifest,
            },
            "ane_w8": {
                "path": portable_path(args.w8),
                "manifest": agents["ane_w8"].manifest,
            },
        },
        "warmup": warmup,
        "answer_agreement": answer_agreement,
        "blocks": [],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    for cycle in range(args.cycles):
        for backend in order:
            block = endpoint_block(
                agents[backend],
                cases,
                args.seconds,
                rate=0,
                expected=warmup[backend]["results"],
            )
            block.update(backend=backend, cycle=cycle)
            report["blocks"].append(block)
            report["summary"] = aggregate(report["blocks"])
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"cycle={cycle} {backend}: "
                f"P50={block['latency']['p50_ms']:.3f} ms "
                f"P95={block['latency']['p95_ms']:.3f} ms "
                f"calls={block['completed_decisions']} "
                f"unstable={block['unstable_rounded_results']}",
                flush=True,
            )
            if args.idle_seconds:
                time.sleep(args.idle_seconds)

    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
