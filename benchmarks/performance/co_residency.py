"""Measure fixed L512 ANE latency before and after loading MLX in the same process."""

from __future__ import annotations

import argparse
import copy
import gc
import json
import statistics
import sys
import time
from pathlib import Path

import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def stats(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)

    def pct(q: float) -> float:
        pos = (len(ordered) - 1) * q
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        w = pos - lo
        return ordered[lo] * (1 - w) + ordered[hi] * w

    return {
        "n": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def measure(agent, cases, warmup: int, iterations: int) -> dict:
    for i in range(warmup):
        agent.predict(*cases[i % len(cases)])
    values = []
    for i in range(iterations):
        started = time.perf_counter()
        agent.predict(*cases[i % len(cases)])
        values.append((time.perf_counter() - started) * 1000.0)
    return stats(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--length", type=int, default=512)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=16)
    parser.add_argument("--iterations", type=int, default=100)
    args = parser.parse_args()

    from laya_coreml.ane import ANEAgent
    from laya_mlx import Agent as MLXAgent

    examples = PROJECT_ROOT / "references/laya-coreml/examples"
    state = json.loads((examples / "state.json").read_text())
    definition = next(
        iter(json.loads((examples / "questions.json").read_text()).values())
    )
    questions = {"q0": definition}
    cases = []
    for suffix in range(8):
        changed = copy.deepcopy(state)
        changed["subject"] = f"Duplicate charge on invoice #441{suffix}"
        cases.append((changed, questions))

    process = psutil.Process()
    started = time.perf_counter()
    ane = ANEAgent(
        args.source,
        package=args.package,
        length=args.length,
        compute_units="cpu_ne",
    )
    ane_load_seconds = time.perf_counter() - started
    rss_after_ane = process.memory_info().rss

    ane_alone = measure(ane, cases, args.warmup, args.iterations)

    started = time.perf_counter()
    mlx = MLXAgent(
        args.source,
        dtype="float16",
        batch_size=1,
        compile=True,
        cache_prompts=True,
        pad_to_multiple=32,
    )
    mlx_load_seconds = time.perf_counter() - started
    mlx_measurement = measure(mlx, cases, args.warmup, args.iterations)
    rss_both = process.memory_info().rss

    ane_with_mlx = measure(ane, cases, args.warmup, args.iterations)

    del mlx
    gc.collect()
    try:
        import mlx.core as mx

        mx.clear_cache()
    except (ImportError, AttributeError):
        pass
    time.sleep(2)
    rss_after_mlx_release = process.memory_info().rss
    ane_after_mlx_release = measure(ane, cases, args.warmup, args.iterations)

    payload = {
        "settings": {
            "source": str(args.source),
            "package": str(args.package),
            "length": args.length,
            "warmup": args.warmup,
            "iterations": args.iterations,
        },
        "ane_load_seconds": ane_load_seconds,
        "mlx_load_seconds": mlx_load_seconds,
        "rss": {
            "after_ane_bytes": rss_after_ane,
            "both_resident_bytes": rss_both,
            "after_mlx_release_bytes": rss_after_mlx_release,
        },
        "latency": {
            "ane_alone": ane_alone,
            "mlx_with_ane_resident": mlx_measurement,
            "ane_with_mlx_resident": ane_with_mlx,
            "ane_after_mlx_release": ane_after_mlx_release,
        },
        "ratios": {
            "ane_with_mlx_over_alone_p50": ane_with_mlx["p50_ms"] / ane_alone["p50_ms"],
            "ane_after_release_over_alone_p50": (
                ane_after_mlx_release["p50_ms"] / ane_alone["p50_ms"]
            ),
            "mlx_over_ane_alone_p50": mlx_measurement["p50_ms"] / ane_alone["p50_ms"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
