"""Resume plan/timing for an already-converted fixed-shape Core ML research package."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

import coremltools as ct
import numpy as np
from benchmarks.common import compute_plan, save, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--compute-units",
        choices=("cpu_ne", "cpu_gpu", "all", "cpu"),
        default="cpu_ne",
    )
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=10)
    args = parser.parse_args()

    report_path = args.output_dir / "report.json"
    package = args.output_dir / "model.mlpackage"
    if not report_path.exists() or not package.exists():
        raise FileNotFoundError(
            "output-dir must contain report.json and model.mlpackage"
        )
    report = json.loads(report_path.read_text())

    units = {
        "cpu_ne": ct.ComputeUnit.CPU_AND_NE,
        "cpu_gpu": ct.ComputeUnit.CPU_AND_GPU,
        "all": ct.ComputeUnit.ALL,
        "cpu": ct.ComputeUnit.CPU_ONLY,
    }[args.compute_units]

    started = time.perf_counter()
    model = ct.models.MLModel(str(package), compute_units=units)
    report["load_compile_seconds"] = time.perf_counter() - started
    report["compute_units"] = args.compute_units
    save(report_path, report)

    report["compute_plan"] = compute_plan(
        SimpleNamespace(model=model, compute_units=args.compute_units)
    )
    save(report_path, report)
    print(
        "PLAN",
        report["compute_plan"]["preferred_operation_counts"],
        "load_compile_s",
        report["load_compile_seconds"],
        flush=True,
    )

    arrays = {}
    for feature in model.get_spec().description.input:
        shape = tuple(feature.type.multiArrayType.shape)
        arrays[feature.name] = np.zeros(shape, dtype=np.float16)

    for _ in range(args.warmup):
        model.predict(arrays)

    values = []
    output = None
    for _ in range(args.iterations):
        started = time.perf_counter()
        output = model.predict(arrays)
        values.append((time.perf_counter() - started) * 1000.0)

    report["timing"] = {**stats(values), "samples_ms": values}
    report["outputs"] = {
        name: {"shape": list(value.shape), "finite": bool(np.isfinite(value).all())}
        for name, value in (output or {}).items()
    }
    save(report_path, report)
    print(
        "TIMING",
        report["timing"]["p50_ms"],
        report["timing"]["p95_ms"],
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
