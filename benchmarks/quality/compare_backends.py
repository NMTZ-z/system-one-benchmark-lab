"""Compare two completed typed-decisions backend runs decision by decision."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

METRICS = (
    "accuracy",
    "soft_accuracy",
    "kl_from_gold",
    "total_variation",
    "brier_vs_soft",
    "ece_15",
    "score_mae",
    "within_1_level",
)


def selected_label(answer: dict[str, Any]) -> str:
    kind = answer["type"]
    if kind == "choice":
        return str(answer["choice"])
    if kind == "noul":
        return "true" if float(answer["noul"]) >= 0.5 else "false"
    probabilities = answer["probabilities"]
    return str(max(probabilities, key=probabilities.get))


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("empty latency values")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def latency_stats(cases: list[dict[str, Any]]) -> dict[str, float]:
    values = [float(case["latency_ms"]) for case in cases if case.get("status") == "ok"]
    return {
        "mean_ms": statistics.fmean(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    left = json.loads(args.left.read_text())
    right = json.loads(args.right.read_text())

    if left["dataset"]["revision"] != right["dataset"]["revision"]:
        raise RuntimeError("dataset revisions differ")
    if left["dataset"]["cases"] != right["dataset"]["cases"]:
        raise RuntimeError("case counts differ")

    right_cases = {case["id"]: case for case in right["cases"]}
    total = 0
    exact_objects = 0
    selected_mismatches: list[dict[str, str]] = []
    max_probability_delta = 0.0
    max_score_delta = 0.0
    max_noul_delta = 0.0
    max_confidence_delta = 0.0
    max_action_probability_delta = 0.0

    for left_case in left["cases"]:
        right_case = right_cases[left_case["id"]]
        if left_case.get("status") != "ok" or right_case.get("status") != "ok":
            raise RuntimeError(f"non-ok case in parity comparison: {left_case['id']}")
        left_answers = left_case["response"]["answers"]
        right_answers = right_case["response"]["answers"]
        if set(left_answers) != set(right_answers):
            raise RuntimeError(f"question sets differ: {left_case['id']}")

        for question, left_answer in left_answers.items():
            right_answer = right_answers[question]
            total += 1
            exact_objects += left_answer == right_answer
            left_selected = selected_label(left_answer)
            right_selected = selected_label(right_answer)
            if left_selected != right_selected:
                selected_mismatches.append(
                    {
                        "case_id": left_case["id"],
                        "question": question,
                        "left": left_selected,
                        "right": right_selected,
                    }
                )

            if left_answer["type"] in ("choice", "score"):
                for key, value in left_answer["probabilities"].items():
                    max_probability_delta = max(
                        max_probability_delta,
                        abs(float(value) - float(right_answer["probabilities"][key])),
                    )
            if left_answer["type"] == "score":
                max_score_delta = max(
                    max_score_delta,
                    abs(float(left_answer["score"]) - float(right_answer["score"])),
                )
            if left_answer["type"] == "noul":
                max_noul_delta = max(
                    max_noul_delta,
                    abs(float(left_answer["noul"]) - float(right_answer["noul"])),
                )

            max_confidence_delta = max(
                max_confidence_delta,
                abs(
                    float(left_answer.get("confidence", 0.0))
                    - float(right_answer.get("confidence", 0.0))
                ),
            )
            left_action = left_answer.get("action", {}).get("act_probability")
            right_action = right_answer.get("action", {}).get("act_probability")
            if left_action is not None and right_action is not None:
                max_action_probability_delta = max(
                    max_action_probability_delta,
                    abs(float(left_action) - float(right_action)),
                )

    metric_deltas = {
        key: float(left["summary"][key]) - float(right["summary"][key])
        for key in METRICS
    }

    left_by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)
    right_by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in left["cases"]:
        left_by_workflow[case["workflow"]].append(case)
    for case in right["cases"]:
        right_by_workflow[case["workflow"]].append(case)

    workflow_latency = {}
    for workflow in sorted(left_by_workflow):
        left_stats = latency_stats(left_by_workflow[workflow])
        right_stats = latency_stats(right_by_workflow[workflow])
        workflow_latency[workflow] = {
            "left": left_stats,
            "right": right_stats,
            "p50_left_over_right": left_stats["p50_ms"] / right_stats["p50_ms"],
            "mean_left_over_right": left_stats["mean_ms"] / right_stats["mean_ms"],
        }

    left_latency = latency_stats(left["cases"])
    right_latency = latency_stats(right["cases"])

    payload = {
        "dataset": left["dataset"],
        "left": {
            "path": str(args.left),
            "backend": left["backend"],
            "backend_info": left["backend_info"],
            "load_seconds": left["load_seconds"],
            "metrics": {key: left["summary"][key] for key in METRICS},
            "latency": left_latency,
        },
        "right": {
            "path": str(args.right),
            "backend": right["backend"],
            "backend_info": right["backend_info"],
            "load_seconds": right["load_seconds"],
            "metrics": {key: right["summary"][key] for key in METRICS},
            "latency": right_latency,
        },
        "parity": {
            "decisions": total,
            "exact_answer_objects": exact_objects,
            "selected_mismatches": len(selected_mismatches),
            "mismatch_examples": selected_mismatches[:20],
            "max_probability_abs_delta": max_probability_delta,
            "max_score_abs_delta": max_score_delta,
            "max_noul_abs_delta": max_noul_delta,
            "max_confidence_abs_delta": max_confidence_delta,
            "max_action_probability_abs_delta": max_action_probability_delta,
            "metric_deltas_left_minus_right": metric_deltas,
        },
        "latency_comparison": {
            "p50_left_over_right": left_latency["p50_ms"] / right_latency["p50_ms"],
            "mean_left_over_right": left_latency["mean_ms"] / right_latency["mean_ms"],
            "load_left_over_right": float(left["load_seconds"])
            / float(right["load_seconds"]),
            "by_workflow": workflow_latency,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["parity"], ensure_ascii=False, indent=2))
    print(json.dumps(payload["latency_comparison"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
