"""Run the public typed-decisions benchmark through one backend."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.jev import JevClient
from benchmarks.quality.metrics import score_records

DATASET_REVISION = "c76749ec58bd8c3d2ea706b31c333a9059c38f90"


def decode_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def load_rows(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows = pq.read_table(path).to_pylist()
    return rows[:limit] if limit else rows


def save_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def make_backend(args: argparse.Namespace):
    if args.backend == "mlx":
        from laya_mlx import Agent

        agent = Agent(Path(args.model), dtype="float16", batch_size=16)
        return agent.predict, {
            "model": args.model,
            "dtype": "float16",
            "batch_size": 16,
        }

    if args.backend == "coreml":
        from laya_coreml import Agent

        agent = Agent(Path(args.model), compute_units=args.compute_units)
        return agent.predict, {"model": args.model, "compute_units": args.compute_units}

    if args.backend == "jev":
        client = JevClient(
            model=args.model,
            api_key_env=args.api_key_env,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        models = client.list_models()
        available = [item.get("name") for item in models.get("models", [])]
        if available and args.model not in available:
            raise RuntimeError(
                f"requested model {args.model!r} is not in /v1/models: {available}"
            )
        return client.predict, {
            "model": args.model,
            "base_url": client.base_url,
            "available_models": models.get("models", []),
        }

    raise ValueError(f"unsupported backend: {args.backend}")


def build_score_records(
    rows: list[dict[str, Any]], case_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {case["id"]: case for case in case_results}
    records: list[dict[str, Any]] = []
    for row in rows:
        case = by_id.get(row["id"])
        questions = decode_json(row["questions"])
        gold = decode_json(row["gold"])
        answers = case.get("response", {}).get("answers", {}) if case else {}
        status = case.get("status", "missing_case") if case else "missing_case"
        for name, question in questions.items():
            records.append(
                {
                    "case_id": row["id"],
                    "workflow": row["workflow"],
                    "question_name": name,
                    "question_type": question["type"],
                    "question": question,
                    "gold": gold[name],
                    "answer": answers.get(name),
                    "status": status if name not in answers else "ok",
                }
            )
    return records


def latency_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        float(case["latency_ms"]) for case in case_results if case.get("status") == "ok"
    ]
    if not values:
        return {"cases": 0}
    ordered = sorted(values)

    def percentile(q: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * q
        lo = int(position)
        hi = min(lo + 1, len(ordered) - 1)
        weight = position - lo
        return ordered[lo] * (1 - weight) + ordered[hi] * weight

    return {
        "cases": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mlx", "coreml", "jev"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT
        / "datasets/typed-decisions/all/test-00000-of-00001.parquet",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--compute-units", default="cpu_gpu")
    parser.add_argument("--api-key-env", default="TYPESAFE_API_KEY")
    parser.add_argument("--base-url")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    rows = load_rows(args.dataset, args.limit)
    started_load = time.perf_counter()
    predict, backend_info = make_backend(args)
    load_seconds = time.perf_counter() - started_load

    payload: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "repo": "LocalLLaMA/typed-decisions",
            "revision": DATASET_REVISION,
            "split": "all/test",
            "path": str(args.dataset.relative_to(PROJECT_ROOT)),
            "cases": len(rows),
            "decisions": sum(int(row["n_questions"]) for row in rows),
        },
        "backend": args.backend,
        "backend_info": backend_info,
        "load_seconds": load_seconds,
        "measurement": (
            "one predict/API call per dataset case; latency includes public API preparation, "
            "synchronous inference/network, calibration and response formatting; model load excluded"
        ),
        "cases": [],
    }

    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text())
        if (
            previous.get("backend") != args.backend
            or previous.get("dataset", {}).get("revision") != DATASET_REVISION
        ):
            raise RuntimeError("resume file does not match backend/dataset revision")
        payload["cases"] = previous.get("cases", [])

    completed = {case["id"] for case in payload["cases"]}
    total_started = time.perf_counter()

    for index, row in enumerate(rows, start=1):
        if row["id"] in completed:
            continue
        state = decode_json(row["state"])
        questions = decode_json(row["questions"])
        case: dict[str, Any] = {
            "id": row["id"],
            "workflow": row["workflow"],
            "n_questions": int(row["n_questions"]),
        }
        started = time.perf_counter()
        try:
            response = predict(state, questions)
            case.update(
                status="ok",
                latency_ms=(time.perf_counter() - started) * 1000.0,
                response=response,
            )
        except Exception as error:  # noqa: BLE001 - backend failures are benchmark outcomes
            case.update(
                status="error",
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error_type=type(error).__name__,
                error=str(error)[:2000],
            )
        payload["cases"].append(case)
        payload["summary"] = score_records(build_score_records(rows, payload["cases"]))
        payload["latency"] = latency_summary(payload["cases"])
        save_atomic(args.output, payload)

        if index % 20 == 0 or case["status"] != "ok":
            elapsed = time.perf_counter() - total_started
            print(
                f"{args.backend}: {index}/{len(rows)} cases, "
                f"status={case['status']}, elapsed={elapsed:.1f}s",
                flush=True,
            )

    payload["elapsed_seconds"] = time.perf_counter() - total_started
    payload["summary"] = score_records(build_score_records(rows, payload["cases"]))
    payload["latency"] = latency_summary(payload["cases"])

    usage = [
        case.get("response", {}).get("usage")
        for case in payload["cases"]
        if isinstance(case.get("response", {}).get("usage"), dict)
    ]
    if usage:
        payload["usage_total"] = {
            "input_tokens": sum(int(item.get("input_tokens", 0)) for item in usage),
            "output_tokens": sum(int(item.get("output_tokens", 0)) for item in usage),
        }

    actual_models = sorted(
        {
            str(case.get("response", {}).get("model"))
            for case in payload["cases"]
            if case.get("response", {}).get("model")
        }
    )
    if actual_models:
        payload["actual_models"] = actual_models

    save_atomic(args.output, payload)
    summary = payload["summary"]
    print(
        f"FINAL {args.backend}: coverage={summary['coverage']:.3f}, "
        f"accuracy={summary.get('accuracy')}, brier={summary.get('brier_vs_soft')}, "
        f"ECE={summary.get('ece_15')}, p50={payload['latency'].get('p50_ms')} ms",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
