#!/usr/bin/env python3
"""Offline-only comparison of conservative Completion policies.

No model/Runtime/Adapter settings are changed. The blind set MUST be frozen
before comparing policies; never tune and retest on the same blind set.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.completion.evaluate import metrics

CANDIDATE_COMPLETE_THRESHOLD = .50  # selected from pilot calibration ONLY


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0., 1.)
    p = k / n
    den = 1 + z*z/n
    centre = (p + z*z/(2*n)) / den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return max(0., centre-half), min(1., centre+half)


def rule_only(trace: dict, state: dict) -> str:
    if trace["deterministic_rule"] is not None:
        return trace["deterministic_rule"]
    if state.get("required_checks_completed") is True and state.get("final_state_verified") is True:
        return "complete"
    return "verify"  # conservative abstain, not a claim that verification truly remains


def raw_hybrid(trace: dict) -> str:
    return trace["deterministic_rule"] or trace["raw_model_decision"] or "verify"


def calibrated_hybrid(trace: dict, state: dict) -> str:
    if trace["deterministic_rule"] is not None:
        return trace["deterministic_rule"]
    if (
        trace["raw_model_decision"] == "complete"
        and (trace["raw_probabilities"] or {}).get("complete", 0) >= CANDIDATE_COMPLETE_THRESHOLD
        and state.get("required_checks_completed") is True
        and state.get("final_state_verified") is True
    ):
        return "complete"
    if trace["raw_model_decision"] == "continue":
        return "continue"
    return "verify"


def compare(trace_path: Path, gold_path: Path) -> dict:
    trace_bytes = trace_path.read_bytes()
    trace_report = json.loads(trace_bytes.decode("utf-8"))
    trace_sha256 = hashlib.sha256(trace_bytes).hexdigest()
    gold_bytes = gold_path.read_bytes()
    gold_sha256 = hashlib.sha256(gold_bytes).hexdigest()
    if trace_report.get("gold_sha256") != gold_sha256:
        raise ValueError("trace/gold corpus SHA-256 mismatch or missing digest")
    traces = trace_report["rows"]
    cases = {r["id"]: r for r in (json.loads(x) for x in gold_bytes.decode("utf-8").splitlines()) if r}
    if len(traces) != len(cases) or {row["id"] for row in traces} != set(cases):
        raise ValueError("trace/gold ID mismatch; comparisons must be paired")
    observed = []
    for trace in traces:
        # Refuse old audit traces that recorded model fail-open as a hard rule.
        if (
            any(
                "fail_open" in str(trace.get(key) or "")
                for key in ("rule_reason", "final_reason")
            )
            or (
                trace.get("deterministic_rule") is not None
                and trace.get("raw_model_decision") is not None
            )
        ):
            raise ValueError("trace contains model fallback misclassified as deterministic rule")
        item = cases[trace["id"]]
        if item["label"] != trace["label"]:
            raise ValueError("trace/gold labels differ")
        state = item["execution_state"]
        observed.append({
            "id": trace["id"], "label": trace["label"], "source": trace["source"],
            "8a": trace["final_decision"],
            "rules": rule_only(trace, state),
            "raw": raw_hybrid(trace),
            "candidate": calibrated_hybrid(trace, state),
        })
    policies = {}
    for name in ("8a", "rules", "raw", "candidate"):
        rows = [dict(row, prediction=row[name]) for row in observed]
        result = metrics(rows)
        n = result["non_complete_support"]
        k = result["premature_completion_count"]
        result["premature_completion_wilson_95"] = wilson(k, n)
        result["premature_completion_zero_one_sided_upper_95"] = (
            1-math.pow(.05,1/n) if k == 0 and n else None
        )
        policies[name] = result
    return {
        "evaluation": "offline-shadow-policy-replay",
        "policies": policies,
        "threshold_calibrated_on_pilot_only": CANDIDATE_COMPLETE_THRESHOLD,
        "matched_case_count": len(observed),
        "gold_sha256": gold_sha256,
        "trace_sha256": trace_sha256,
        "privacy": "no case task/results or prompt text written",
        "limitations": [
            "original 8A and synthetic pilot are not agent E2E experiments",
            "calibrated candidate requires explicit evidence flags absent from current adapters",
            "zero false completes on a small pilot is not authorization for Active",
        ],
        "paired_predictions": observed,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    report = compare(args.trace, args.gold)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "cases": report["matched_case_count"],
        "results": {k: {"accuracy": v["accuracy"], "macro_f1": v["macro_f1"],
                        "complete_recall": v["per_class"]["complete"]["recall"],
                        "premature": v["premature_completion_count"],
                        "premature_upper95": v["premature_completion_wilson_95"][1]}
                    for k, v in report["policies"].items()}
    }, indent=2))


if __name__ == "__main__":
    main()
