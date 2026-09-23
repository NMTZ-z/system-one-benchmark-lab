"""Validate a Phase 4 fixed-shape ANE body without recomputing a compute plan."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from benchmarks.cases import workload
from benchmarks.common import calibrated, environment, save, softmax, stats
from experiments.ane_engineering.runtime import ANEAgent
from laya_coreml.inputs import collate_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--name", default="laya-typed-decisions")
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--max-probability-error", type=float, default=0.02)
    args = parser.parse_args()

    reference_path = (
        Path(__file__).resolve().parents[2]
        / "references/laya-coreml/benchmarks/results/reference.json"
    )
    reference = json.loads(reference_path.read_text())["models"][args.name]

    started = time.perf_counter()
    agent = ANEAgent(
        args.source, args.package, length=args.length, compute_units="cpu_ne"
    )
    load_compile_seconds = time.perf_counter() - started

    if (
        reference["source_weights_sha256"]
        != agent.manifest["source_files_sha256"]["model.safetensors"]
    ):
        raise ValueError(
            "Golden reference and artifact use different checkpoint weights"
        )

    report = {
        "environment": environment(),
        "name": args.name,
        "length": args.length,
        "package": str(args.package),
        "source": str(args.source),
        "load_compile_seconds": load_compile_seconds,
        "cases": [],
        "passed": False,
        "gate": {
            "argmax": "all evaluated questions agree",
            "max_probability_error": args.max_probability_error,
            "max_action_probability_error": args.max_probability_error,
            "finite_outputs": True,
            "unchanged_token_usage": True,
            "repeated_results_identical": True,
        },
    }

    repeat_cases = []
    for entry in reference["cases"]:
        items, _ = agent.prepare(entry["state"], entry["questions"])
        assert items == entry["items"]
        max_tokens = max(len(item["ids"]) for item in items)
        if max_tokens > args.length:
            report["cases"].append(
                {"case": entry["name"], "skipped": True, "max_tokens": max_tokens}
            )
            continue

        row = {
            "case": entry["name"],
            "max_tokens": max_tokens,
            "questions": len(items),
            "argmax_agree": 0,
            "max_probability_error": 0.0,
            "max_action_probability_error": 0.0,
            "max_action_logit_error": 0.0,
            "max_logit_error": 0.0,
        }
        for index, item in enumerate(items):
            batch = collate_items([item], agent.tok.pad_token_id, shape=agent.shape)
            logits, action = agent.forward(batch)
            if not np.isfinite(logits).all() or not np.isfinite(action).all():
                raise FloatingPointError("Nonfinite ANE result")

            actual_p = calibrated(agent, logits[0], item)
            reference_p = calibrated(agent, entry["logits"][index], item)
            row["argmax_agree"] += int(actual_p.argmax() == reference_p.argmax())
            row["max_probability_error"] = max(
                row["max_probability_error"],
                float(np.abs(actual_p - reference_p).max()),
            )
            row["max_action_probability_error"] = max(
                row["max_action_probability_error"],
                float(
                    np.abs(
                        softmax(action[0]) - softmax(entry["action_logits"][index])
                    ).max()
                ),
            )
            row["max_action_logit_error"] = max(
                row["max_action_logit_error"],
                float(
                    np.abs(action[0] - np.asarray(entry["action_logits"][index])).max()
                ),
            )
            count = len(item["markers"])
            row["max_logit_error"] = max(
                row["max_logit_error"],
                float(
                    np.abs(
                        logits[0, :count] - np.asarray(entry["logits"][index][:count])
                    ).max()
                ),
            )

        result = agent.predict(entry["state"], entry["questions"])
        assert result["usage"] == entry["result"]["usage"]
        repeat_cases.append((entry["state"], entry["questions"], result))
        report["cases"].append(row)
        save(args.output, report)
        print(row, flush=True)

    if not repeat_cases:
        raise RuntimeError("no reference cases fit the fixed shape")

    stable = True
    for index in range(args.repeats):
        state, questions, expected = repeat_cases[index % len(repeat_cases)]
        stable &= agent.predict(state, questions) == expected
    report["repeat"] = {
        "calls": args.repeats,
        "identical_rounded_results": bool(stable),
    }

    state, questions = workload(1)
    for _ in range(10):
        agent.predict(state, questions)
    values = []
    for _ in range(50):
        started = time.perf_counter()
        agent.predict(state, questions)
        values.append((time.perf_counter() - started) * 1000)
    report["short1_end_to_end"] = {**stats(values), "samples_ms": values}

    completed = [row for row in report["cases"] if not row.get("skipped")]
    report["completed_cases"] = len(completed)
    report["skipped_cases"] = len(report["cases"]) - len(completed)
    report["total_questions"] = sum(row["questions"] for row in completed)
    report["argmax_agreements"] = sum(row["argmax_agree"] for row in completed)
    report["max_probability_error"] = max(
        row["max_probability_error"] for row in completed
    )
    report["max_action_probability_error"] = max(
        row["max_action_probability_error"] for row in completed
    )
    report["max_logit_error"] = max(row["max_logit_error"] for row in completed)
    report["max_action_logit_error"] = max(
        row["max_action_logit_error"] for row in completed
    )
    report["passed"] = bool(
        report["argmax_agreements"] == report["total_questions"]
        and report["max_probability_error"] <= args.max_probability_error
        and report["max_action_probability_error"] <= args.max_probability_error
        and stable
    )
    save(args.output, report)
    print(
        "SUMMARY",
        report["argmax_agreements"],
        "/",
        report["total_questions"],
        "prob_err",
        report["max_probability_error"],
        "action_prob_err",
        report["max_action_probability_error"],
        "repeat",
        stable,
        "p50",
        report["short1_end_to_end"]["p50_ms"],
        "load_compile_s",
        report["load_compile_seconds"],
        flush=True,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
