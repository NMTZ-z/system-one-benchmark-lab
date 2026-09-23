#!/usr/bin/env python3
"""Benchmark a published Laya ANE bundle with the upstream short workload."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = PROJECT_ROOT / "references" / "laya-coreml"
if str(UPSTREAM) not in sys.path:
    sys.path.insert(0, str(UPSTREAM))

import laya_coreml as laya
from benchmarks.cases import workload


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return resolved.name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timing_stats(values: list[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "mean_ms": float(array.mean()),
        "stdev_ms": float(array.std(ddof=1)) if len(values) > 1 else 0.0,
        "min_ms": float(array.min()),
        "p50_ms": float(np.percentile(array, 50)),
        "p95_ms": float(np.percentile(array, 95)),
        "p99_ms": float(np.percentile(array, 99)),
        "max_ms": float(array.max()),
        "samples_ms": values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--compute-units", default="cpu_ne", choices=("cpu_ne", "cpu_gpu", "cpu", "all"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.iterations < 1 or args.warmup < 0:
        parser.error("iterations must be positive and warmup must be nonnegative")

    model_dir = args.model_dir.resolve()
    config_path = model_dir / "coreml_config.json"
    if not config_path.is_file():
        raise FileNotFoundError(config_path)

    process = psutil.Process()
    load_start = time.perf_counter()
    agent = laya.load(
        model_dir,
        local_files_only=True,
        compute_units=args.compute_units,
    )
    load_seconds = time.perf_counter() - load_start

    state, questions = workload(1)
    prepared, _ = agent.prepare(state, questions)

    first_start = time.perf_counter()
    expected = agent.predict(state, questions)
    first_prediction_ms = (time.perf_counter() - first_start) * 1000.0

    for _ in range(args.warmup):
        current = agent.predict(state, questions)
        if current != expected:
            raise RuntimeError("unstable warmup output")

    rss_before = process.memory_info().rss
    samples: list[float] = []
    stable = True
    for _ in range(args.iterations):
        start = time.perf_counter()
        current = agent.predict(state, questions)
        samples.append((time.perf_counter() - start) * 1000.0)
        stable &= current == expected
    rss_after = process.memory_info().rss

    stats = timing_stats(samples)
    report = {
        "schema_version": 1,
        "benchmark": "published-laya-ane-short-decision",
        "measurement": (
            "complete predict wall time including prompt construction, tokenization, "
            "input arrays, host embedding lookup, synchronous Core ML inference, "
            "CPU action head, calibration and formatting; excludes model load and warmup"
        ),
        "machine": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version,
        },
        "model": {
            "path": portable_path(model_dir),
            "revision": args.revision,
            "coreml_config_sha256": sha256_file(config_path),
            "manifest": agent.manifest,
            "compute_units": args.compute_units,
        },
        "input": {
            "workload": "upstream benchmarks.cases.workload(1)",
            "questions": 1,
            "actual_token_lengths": [len(item["ids"]) for item in prepared],
        },
        "load_seconds": load_seconds,
        "first_prediction_ms": first_prediction_ms,
        "warmup_calls": args.warmup,
        "timing": stats,
        "decisions_per_second": 1000.0 / stats["mean_ms"],
        "stable_rounded_results": stable,
        "rss_before": rss_before,
        "rss_after": rss_after,
        "example_result": expected,
    }

    if not stable:
        raise RuntimeError("measured outputs were not stable")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"P50={stats['p50_ms']:.3f} ms "
        f"P95={stats['p95_ms']:.3f} ms "
        f"P99={stats['p99_ms']:.3f} ms "
        f"mean={stats['mean_ms']:.3f} ms "
        f"stable={stable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
