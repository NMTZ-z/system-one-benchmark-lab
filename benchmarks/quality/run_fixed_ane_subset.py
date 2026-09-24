"""Run the public typed-decisions benchmark on a fixed-shape ANE research body.

Each decision is evaluated independently so decisions that exceed the fixed
sequence length are reported as over-capacity rather than counted as wrong.
Optionally compare every supported ANE answer against a frozen backend run.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.quality.compare_backends import selected_label
from benchmarks.quality.metrics import score_records
from benchmarks.quality.run_typed_decisions import (
    DATASET_REVISION,
    decode_json,
    save_atomic,
)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty values")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def latency_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        float(record["latency_ms"])
        for record in records
        if record.get("status") == "ok" and record.get("latency_ms") is not None
    ]
    if not values:
        return {"decisions": 0}
    return {
        "decisions": len(values),
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def score_input(
    rows: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    reference: bool = False,
) -> list[dict[str, Any]]:
    by_key = {(item["case_id"], item["question_name"]): item for item in decisions}
    records: list[dict[str, Any]] = []
    for row in rows:
        questions = decode_json(row["questions"])
        gold = decode_json(row["gold"])
        for name, question in questions.items():
            item = by_key.get((row["id"], name))
            answer_key = "reference_answer" if reference else "answer"
            status = item.get("status", "missing") if item else "missing"
            answer = item.get(answer_key) if item and status == "ok" else None
            records.append(
                {
                    "case_id": row["id"],
                    "workflow": row["workflow"],
                    "question_name": name,
                    "question_type": question["type"],
                    "question": question,
                    "gold": gold[name],
                    "answer": answer,
                    "status": status,
                }
            )
    return records


def compare_answers(
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    compared = 0
    selected_mismatches: list[dict[str, Any]] = []
    max_probability_delta = 0.0
    max_score_delta = 0.0
    max_noul_delta = 0.0
    max_confidence_delta = 0.0
    max_action_probability_delta = 0.0

    for item in decisions:
        if item.get("status") != "ok":
            continue
        left = item.get("answer")
        right = item.get("reference_answer")
        if not isinstance(left, dict) or not isinstance(right, dict):
            continue
        compared += 1
        left_selected = selected_label(left)
        right_selected = selected_label(right)
        if left_selected != right_selected:
            selected_mismatches.append(
                {
                    "case_id": item["case_id"],
                    "workflow": item["workflow"],
                    "question_name": item["question_name"],
                    "question_type": item["question_type"],
                    "tokens": item["tokens"],
                    "ane_selected": left_selected,
                    "reference_selected": right_selected,
                }
            )

        if left["type"] in ("choice", "score"):
            for key, value in left["probabilities"].items():
                max_probability_delta = max(
                    max_probability_delta,
                    abs(float(value) - float(right["probabilities"][key])),
                )
        if left["type"] == "score":
            max_score_delta = max(
                max_score_delta, abs(float(left["score"]) - float(right["score"]))
            )
        if left["type"] == "noul":
            max_noul_delta = max(
                max_noul_delta, abs(float(left["noul"]) - float(right["noul"]))
            )

        max_confidence_delta = max(
            max_confidence_delta,
            abs(
                float(left.get("confidence", 0.0)) - float(right.get("confidence", 0.0))
            ),
        )
        left_action = left.get("action", {}).get("act_probability")
        right_action = right.get("action", {}).get("act_probability")
        if left_action is not None and right_action is not None:
            max_action_probability_delta = max(
                max_action_probability_delta,
                abs(float(left_action) - float(right_action)),
            )

    return {
        "decisions_compared": compared,
        "selected_mismatches": len(selected_mismatches),
        "selected_agreements": compared - len(selected_mismatches),
        "selected_agreement_rate": (
            (compared - len(selected_mismatches)) / compared if compared else None
        ),
        "max_probability_abs_delta": max_probability_delta,
        "max_score_abs_delta": max_score_delta,
        "max_noul_abs_delta": max_noul_delta,
        "max_confidence_abs_delta": max_confidence_delta,
        "max_action_probability_abs_delta": max_action_probability_delta,
        "mismatch_examples": selected_mismatches[:50],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument(
        "--min-tokens-exclusive",
        type=int,
        default=0,
        help="Only execute decisions with token length > this value; smaller decisions are router_skip.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT
        / "datasets/typed-decisions/all/test-00000-of-00001.parquet",
    )
    parser.add_argument("--reference-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--save-every", type=int, default=20)
    args = parser.parse_args()

    from experiments.ane_engineering.runtime import ANEAgent

    rows = pq.read_table(args.dataset).to_pylist()
    reference_cases: dict[str, dict[str, Any]] = {}
    if args.reference_run:
        reference_payload = json.loads(args.reference_run.read_text())
        if reference_payload.get("dataset", {}).get("revision") != DATASET_REVISION:
            raise RuntimeError("reference run uses a different dataset revision")
        reference_cases = {case["id"]: case for case in reference_payload["cases"]}

    started = time.perf_counter()
    agent = ANEAgent(
        args.source, args.package, length=args.length, compute_units="cpu_ne"
    )
    load_compile_seconds = time.perf_counter() - started

    payload: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backend": "ane_research_fixed",
        "backend_info": {
            "source": str(args.source),
            "package": str(args.package),
            "length": args.length,
            "min_tokens_exclusive": args.min_tokens_exclusive,
            "compute_units": "cpu_ne",
            "package_sha256": agent.manifest.get("package_sha256"),
        },
        "dataset": {
            "repo": "LocalLLaMA/typed-decisions",
            "revision": DATASET_REVISION,
            "split": "all/test",
            "path": str(args.dataset.relative_to(PROJECT_ROOT)),
            "cases": len(rows),
            "decisions": sum(int(row["n_questions"]) for row in rows),
        },
        "reference_run": str(args.reference_run) if args.reference_run else None,
        "load_compile_seconds": load_compile_seconds,
        "measurement": (
            "one predict call per decision; fixed-shape capacity is checked before inference; "
            "model load/compile excluded from per-decision latency"
        ),
        "decisions": [],
    }

    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text())
        if (
            previous.get("dataset", {}).get("revision") != DATASET_REVISION
            or previous.get("backend_info", {}).get("length") != args.length
            or previous.get("backend_info", {}).get("min_tokens_exclusive", 0)
            != args.min_tokens_exclusive
            or previous.get("backend_info", {}).get("package_sha256")
            != agent.manifest.get("package_sha256")
        ):
            raise RuntimeError("resume file does not match dataset/shape/package")
        payload["decisions"] = previous.get("decisions", [])

    completed = {
        (item["case_id"], item["question_name"]) for item in payload["decisions"]
    }
    counters: Counter[str] = Counter(item["status"] for item in payload["decisions"])
    total_started = time.perf_counter()
    processed_since_save = 0

    for row in rows:
        state = decode_json(row["state"])
        questions = decode_json(row["questions"])
        reference_answers = (
            reference_cases.get(row["id"], {}).get("response", {}).get("answers", {})
        )
        for name, question in questions.items():
            if (row["id"], name) in completed:
                continue

            items, _ = agent.prepare(state, {name: question})
            item = items[0]
            tokens = len(item["ids"])
            options = len(item["markers"])
            record: dict[str, Any] = {
                "case_id": row["id"],
                "workflow": row["workflow"],
                "question_name": name,
                "question_type": question["type"],
                "tokens": tokens,
                "options": options,
                "reference_answer": reference_answers.get(name),
            }

            if tokens <= args.min_tokens_exclusive:
                record["status"] = "router_skip"
                counters["router_skip"] += 1
            elif tokens > args.length or options > 32:
                record["status"] = "over_capacity"
                counters["over_capacity"] += 1
            else:
                started = time.perf_counter()
                try:
                    response = agent.predict(state, {name: question})
                    elapsed_ms = (time.perf_counter() - started) * 1000.0
                    record.update(
                        status="ok",
                        latency_ms=elapsed_ms,
                        answer=response["answers"][name],
                        usage=response.get("usage"),
                    )
                    counters["ok"] += 1
                except Exception as error:  # noqa: BLE001 - inference failures are outcomes
                    record.update(
                        status="error",
                        latency_ms=(time.perf_counter() - started) * 1000.0,
                        error_type=type(error).__name__,
                        error=str(error)[:2000],
                    )
                    counters["error"] += 1

            payload["decisions"].append(record)
            processed_since_save += 1
            if processed_since_save >= args.save_every:
                payload["latency"] = latency_summary(payload["decisions"])
                save_atomic(args.output, payload)
                processed_since_save = 0

            total_done = len(payload["decisions"])
            if total_done % 100 == 0 or record["status"] == "error":
                print(
                    f"fixed-ane L{args.length}: {total_done}/"
                    f"{payload['dataset']['decisions']} decisions "
                    f"ok={counters['ok']} over={counters['over_capacity']} "
                    f"errors={counters['error']} elapsed={time.perf_counter() - total_started:.1f}s",
                    flush=True,
                )

    payload["elapsed_seconds"] = time.perf_counter() - total_started
    payload["latency"] = latency_summary(payload["decisions"])
    payload["status_counts"] = dict(sorted(counters.items()))
    payload["ane_summary"] = score_records(score_input(rows, payload["decisions"]))
    if reference_cases:
        payload["reference_subset_summary"] = score_records(
            score_input(rows, payload["decisions"], reference=True)
        )
        payload["parity"] = compare_answers(payload["decisions"])

    by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in payload["decisions"]:
        by_workflow[item["workflow"]].append(item)
        by_type[item["question_type"]].append(item)
    payload["latency_by_workflow"] = {
        key: latency_summary(value) for key, value in sorted(by_workflow.items())
    }
    payload["latency_by_question_type"] = {
        key: latency_summary(value) for key, value in sorted(by_type.items())
    }

    save_atomic(args.output, payload)
    print(
        f"FINAL L{args.length}: {payload['status_counts']} "
        f"p50={payload['latency'].get('p50_ms')} "
        f"accuracy={payload['ane_summary'].get('accuracy')} "
        f"mismatches={payload.get('parity', {}).get('selected_mismatches')}",
        flush=True,
    )
    return 0 if counters["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
