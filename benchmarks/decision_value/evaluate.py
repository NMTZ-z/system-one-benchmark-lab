#!/usr/bin/env python3
"""Independent, privacy-safe Phase 8.3 paired-decision evaluator.

This consumes *captured* decisions; it never generates model predictions,
executes an Agent action, accesses Provider credentials or claims savings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from local_system_one.decision_opportunity import ALLOWED_LABELS, evaluate_opportunity

SCHEMA = "local-system-one/decision-value-case-v1"
FREEZE_SCHEMA = "local-system-one/decision-value-freeze-v1"
REPORT_SCHEMA = "local-system-one/decision-value-report-v1"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
MAX_CASES = 10_000
MAX_BYTES = 8_000_000


class EvaluationError(ValueError):
    """A paired comparison is unverifiable or inconsistent."""


def _strict(obj: Any, keys: set[str], where: str) -> dict:
    if not isinstance(obj, dict) or set(obj) - keys:
        raise EvaluationError(f"invalid or unexpected fields in {where}")
    return obj


def _name(v: Any) -> bool:
    return isinstance(v, str) and bool(NAME.fullmatch(v))


def _choice(v: Any, name: str) -> str:
    if not isinstance(v, str) or v not in ALLOWED_LABELS:
        raise EvaluationError(f"{name} is not a registered choice")
    return v


def _bool(v: Any, name: str) -> bool:
    if type(v) is not bool:
        raise EvaluationError(f"{name} must be boolean")
    return v


def _latency(v: Any, name: str) -> float | None:
    if v is None:
        return None
    if (isinstance(v, bool) or not isinstance(v, (int, float))
        or not math.isfinite(v) or not 0 <= v <= 86_400_000):
        raise EvaluationError(f"{name} is not a bounded measured duration")
    return float(v)


def _rate(k: int, n: int) -> float | None:
    return round(k / n, 6) if n else None


def _wilson(k: int, n: int) -> list[float] | None:
    if not n:
        return None
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    mid = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [round(max(0, mid-half), 6), round(min(1, mid+half), 6)]


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    vs = sorted(values)
    index = (len(vs)-1)*p
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return round(vs[lo], 3)
    return round(vs[lo]*(hi-index)+vs[hi]*(index-lo), 3)


def validate_case(record: Any) -> dict:
    """Check the case's three baseline observations share a single frozen input.

    Native decision quality is only calculable if an independent decision
    adjudication exists. A verified native task outcome is not that adjudication.
    """
    row = _strict(record, {
        "schema", "case_id", "gate", "source", "split",
        "standardized_input_sha256", "gold", "opportunity",
        "rule_only", "rules_model", "native", "safety",
    }, "case")
    if row.get("schema") != SCHEMA or not _name(row.get("case_id")) or not _name(row.get("gate")):
        raise EvaluationError("invalid case schema/name")
    if row.get("source") not in {
        "synthetic", "fault_injection", "public_reconstruction", "real_agent",
    } or row.get("split") not in {
        "development", "calibration", "historical_holdout",
        "frozen_holdout", "adversarial", "native_acceptance",
    }:
        raise EvaluationError("invalid source/split; cannot pool provenance")
    if not isinstance(row.get("standardized_input_sha256"), str) or not HEX64.fullmatch(
        row["standardized_input_sha256"]
    ):
        raise EvaluationError("missing frozen standardized-input digest")

    gold = _strict(row.get("gold"), {"acceptable", "preferred", "oracle"}, "gold")
    acceptable = gold.get("acceptable")
    if (not isinstance(acceptable, list) or not acceptable
        or len(acceptable) > 12 or
        any(not isinstance(x, str) or x not in ALLOWED_LABELS for x in acceptable) or
        len(set(acceptable)) != len(acceptable)):
        raise EvaluationError("invalid acceptable gold labels")
    preferred = gold.get("preferred")
    if preferred is not None and preferred not in acceptable:
        raise EvaluationError("preferred gold must be acceptable")
    if gold.get("oracle") not in {"synthetic_editorial", "reconstruction_editorial", "fault_oracle", "independent_task_and_decision"}:
        raise EvaluationError("gold provenance must be explicit")
    if row["source"] == "real_agent" and gold["oracle"] != "independent_task_and_decision":
        raise EvaluationError("real cases need an independent decision oracle")
    if (row["source"], gold["oracle"]) in {("synthetic", "independent_task_and_decision"), ("public_reconstruction", "independent_task_and_decision"), ("fault_injection", "independent_task_and_decision")} or (row["source"] == "synthetic" and gold["oracle"] != "synthetic_editorial") or (row["source"] == "public_reconstruction" and gold["oracle"] != "reconstruction_editorial") or (row["source"] == "fault_injection" and gold["oracle"] != "fault_oracle"):
        raise EvaluationError("synthetic editorial labels cannot be called real oracle")

    opportunity = evaluate_opportunity(row.get("opportunity"))
    if opportunity["gate"] != row["gate"]:
        raise EvaluationError("gate/opportunity identity mismatch")
    rule = _strict(row.get("rule_only"), {"decision"}, "rule-only")
    b = _choice(rule.get("decision"), "rule-only decision")
    if opportunity["category"] == "rule_only" and b != opportunity["rule_decision"]:
        raise EvaluationError("rule-only decision disagrees with trusted rule")

    candidate = _strict(row.get("rules_model"), {
        "guarded_decision", "raw_model_decision", "decision_source", "backend",
        "model_invoked", "model_completed", "safety_override", "model_latency_ms",
        "failure_fallback", "model_output_invalid",
    }, "rules+model")
    final = _choice(candidate.get("guarded_decision"), "guarded decision")
    attempted = _bool(candidate.get("model_invoked"), "model_invoked")
    completed = _bool(candidate.get("model_completed"), "model_completed")
    override = _bool(candidate.get("safety_override"), "safety_override")
    invalid_output = _bool(candidate.get("model_output_invalid"), "model_output_invalid")
    failure_fallback = candidate.get("failure_fallback")
    raw = candidate.get("raw_model_decision")
    if candidate.get("decision_source") not in {"rule", "model"}:
        raise EvaluationError("bad decision source")
    if candidate.get("backend") not in {"rule", "mlx", "ane", "other_local", "unknown"}:
        raise EvaluationError("unrecognized execution backend")
    _latency(candidate.get("model_latency_ms"), "model_latency_ms")

    if completed and not attempted:
        raise EvaluationError("completed inference without a model attempt")
    if invalid_output and not (attempted and completed):
        raise EvaluationError("invalid output requires completed model work")
    if attempted and opportunity["category"] != "typed_model_candidate":
        raise EvaluationError("model attempted outside eligible opportunity")
    if attempted and candidate["backend"] == "rule":
        raise EvaluationError("model attempt cannot be recorded as zero backend")
    if completed and not invalid_output:
        if failure_fallback is not None:
            raise EvaluationError("successful model cannot claim an inference failure")
        _choice(raw, "raw model decision")
        if candidate["backend"] not in {"mlx", "ane", "other_local"}:
            raise EvaluationError("completed local inference has unknown backend")
        if override != (raw != final):
            raise EvaluationError("raw/guarded safety override mismatch")
        if final == raw and candidate["decision_source"] != "model":
            raise EvaluationError("unmodified completed model decision must retain model source")
        if (final not in opportunity["candidate_labels"] and final != b):
            raise EvaluationError("guarded choice is outside prechecked candidates")
    else:
        if raw is not None or override or candidate["decision_source"] != "rule":
            raise EvaluationError("invalid output/fallback may not invent raw inference")
        if invalid_output and not (attempted and completed):
            raise EvaluationError("malformed output requires completed model invocation")
        if failure_fallback == "completion_fail_open_continue":
            if row["gate"] != "completion" or final != "continue" or not attempted:
                raise EvaluationError("invalid conservative Completion fail-open")
        elif failure_fallback == "retry_rule_fallback":
            if row["gate"] != "retry_escalation" or final != b or not attempted:
                raise EvaluationError("invalid Retry model failure fallback")
        elif failure_fallback is None:
            if (attempted and not invalid_output) or final != b:
                raise EvaluationError("unrecorded model failure or silent rule fallback")
        else:
            raise EvaluationError("unrecognized failure fallback")
    if opportunity["category"] == "rule_only" and final != opportunity["rule_decision"]:
        raise EvaluationError("deterministic safety result cannot be overridden")

    native = _strict(row.get("native"), {
        "decision", "decision_independently_adjudicated", "task_success",
        "task_outcome_independently_verified", "provider_attempts",
    }, "native")
    nd = native.get("decision")
    if nd is not None:
        _choice(nd, "native decision")
    independent = _bool(native.get("decision_independently_adjudicated"), "native adjudication")
    verified = _bool(native.get("task_outcome_independently_verified"), "native task oracle")
    task_success = native.get("task_success")
    if task_success is not None and type(task_success) is not bool:
        raise EvaluationError("native task_success must be boolean or unknown")
    if independent and nd is None:
        raise EvaluationError("native adjudication requires native decision")
    if verified != (task_success is not None):
        raise EvaluationError("native task outcome must have independent proof")
    attempts = native.get("provider_attempts")
    if attempts is not None and (type(attempts) is not int or not 0 <= attempts <= 100_000):
        raise EvaluationError("invalid observed Provider request count")
    if row["source"] != "real_agent" and (nd is not None or verified or attempts is not None):
        raise EvaluationError("synthetic observations cannot impersonate native Agent")
    if independent and gold["oracle"] != "independent_task_and_decision":
        raise EvaluationError("native labels need independent oracle")

    safety = _strict(row.get("safety"), {"retry_forbidden_by_policy"}, "safety")
    _bool(safety.get("retry_forbidden_by_policy"), "retry_forbidden_by_policy")
    if safety["retry_forbidden_by_policy"] and "retry_same" in acceptable:
        raise EvaluationError("gold contains policy-forbidden retry")
    return {**row, "_derived_opportunity": opportunity}


def _policy_quality(rows: list[dict], policy: str) -> dict:
    n = len(rows)
    def pred(r):
        return (
            r["rule_only"]["decision"] if policy == "rule_only" else
            r["rules_model"]["guarded_decision"] if policy == "rules_model" else
            r["native"]["decision"]
        )
    compared = [r for r in rows if pred(r) is not None and (
        policy != "native" or r["native"]["decision_independently_adjudicated"]
    )]
    hits = sum(pred(r) in r["gold"]["acceptable"] for r in compared)
    preferred = [r for r in compared if r["gold"]["preferred"] is not None]
    result = {
        "observed": len(compared),
        "acceptable_accuracy": _rate(hits, len(compared)),
        "preferred_accuracy": _rate(sum(pred(r) == r["gold"]["preferred"] for r in preferred), len(preferred)),
        "uncertainty_wilson95": _wilson(hits, len(compared)),
    }
    gate = rows[0]["gate"]
    if gate == "completion":
        eligible = [r for r in compared if "complete" not in r["gold"]["acceptable"]]
        complete = [r for r in compared if pred(r) == "complete"]
        correct_complete = sum("complete" in r["gold"]["acceptable"] for r in complete)
        actual_complete = [r for r in compared if "complete" in r["gold"]["acceptable"]]
        result.update({
            "complete_precision": _rate(correct_complete, len(complete)),
            "complete_recall": _rate(sum(pred(r) == "complete" for r in actual_complete), len(actual_complete)),
            "premature_completion_rate": _rate(sum(pred(r) == "complete" for r in eligible), len(eligible)),
            "premature_count": sum(pred(r) == "complete" for r in eligible),
            "non_complete_support": len(eligible),
        })
    if gate == "retry_escalation":
        forbidden = [r for r in compared if r["safety"]["retry_forbidden_by_policy"]]
        verification = [r for r in compared if r["gold"]["preferred"] == "verify_state"]
        result.update({
            "unsafe_retry_rate": _rate(sum(pred(r) == "retry_same" for r in forbidden), len(forbidden)),
            "unsafe_retry_denominator": len(forbidden),
            "missed_verification_rate": _rate(sum(pred(r) != "verify_state" for r in verification), len(verification)),
            "unnecessary_escalation_rate": _rate(sum(pred(r) == "escalate_model" and
                "escalate_model" not in r["gold"]["acceptable"] for r in compared), len(compared)),
        })
    return result


def evaluate_rows(cases: list[dict]) -> dict:
    if not cases or len(cases) > MAX_CASES:
        raise EvaluationError("case collection is empty or too large")
    valid = [validate_case(r) for r in cases]
    ids = [r["case_id"] for r in valid]
    if len(set(ids)) != len(ids):
        raise EvaluationError("duplicate case ID, including cross-source/split collisions")
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in valid:
        grouped[(r["gate"], r["source"], r["split"])].append(r)
    output = {}
    for (gate, source, split), rows in sorted(grouped.items()):
        cats = Counter(r["_derived_opportunity"]["category"] for r in rows)
        attempted = [r for r in rows if r["rules_model"]["model_invoked"]]
        completed = [r for r in attempted if r["rules_model"]["model_completed"]]
        overridden = [r for r in completed if r["rules_model"]["safety_override"]]
        verified = [r for r in rows if r["native"]["task_outcome_independently_verified"]]
        latency = [r["rules_model"]["model_latency_ms"] for r in attempted
                   if r["rules_model"]["model_latency_ms"] is not None]
        native_known = [r["native"]["provider_attempts"] for r in rows
                        if r["native"]["provider_attempts"] is not None]
        output["/".join((gate, source, split))] = {
            "gate": gate, "source": source, "split": split, "n": len(rows),
            "opportunity_categories": dict(sorted(cats.items())),
            "rule_only_coverage": _rate(cats["rule_only"], len(rows)),
            "typed_opportunity_coverage": _rate(cats["typed_model_candidate"], len(rows)),
            "model_attempted": len(attempted),
            "model_completed": len(completed),
            "model_participation_rate": _rate(len(attempted), len(rows)),
            "model_attempts_among_candidates": _rate(len(attempted), cats["typed_model_candidate"]),
            "safety_overrides": len(overridden),
            "rule_only_quality": _policy_quality(rows, "rule_only"),
            "rules_model_quality": _policy_quality(rows, "rules_model"),
            "native_decision_quality": _policy_quality(rows, "native"),
            "native_verified_task_outcomes": len(verified),
            "native_verified_task_successes": sum(r["native"]["task_success"] is True for r in verified),
            "observed_provider_attempts": sum(native_known) if len(native_known) == len(rows) else None,
            "model_latency_p50_ms": _percentile(latency, .5),
            "model_latency_p95_ms": _percentile(latency, .95),
            "model_latency_n": len(latency),
            "latency_small_sample": len(latency) < 30,
            "real_agent_savings": "NOT_MEASURED",
        }
    return {
        "schema": REPORT_SCHEMA,
        "baseline_names": ["Native Agent", "Rule-only", "Rules + Model"],
        "groups": output,
        "grouping_rule": "never pool gate/source/split",
        "active_authority": "NOT_AUTHORIZED",
        "actual_agent_savings": "NOT_MEASURED",
        "limitations": [
            "Shadow-only decisions cannot establish actual Agent-level savings.",
            "Synthetic editorial oracle labels are not independent real-world task outcomes.",
            "Native task success and native decision quality are distinct; missing is null.",
            "Opportunity schema and hashes cannot authenticate fabricated evidence.",
            "Historical/observed splits are not a newly independent blind test.",
        ],
    }


def evaluate_file(dataset: Path, manifest: Path, protocol: Path) -> dict:
    data = dataset.read_bytes()
    if len(data) > MAX_BYTES:
        raise EvaluationError("dataset exceeds byte cap")
    freeze = json.loads(manifest.read_text(encoding="utf-8"))
    _strict(freeze, {
        "schema", "dataset_sha256", "protocol_sha256", "source_commit",
        "freeze_kind", "evaluator_sha256", "model_identity", "requested_backend", "case_count",
    }, "freeze manifest")
    if freeze.get("schema") != FREEZE_SCHEMA or freeze.get("freeze_kind") not in {
        "synthetic_development", "historical_observed", "new_frozen_holdout",
    } or not isinstance(freeze.get("source_commit"), str) or not re.fullmatch(r"[a-f0-9]{40}", freeze["source_commit"]):
        raise EvaluationError("invalid freeze declaration")
    if (not isinstance(freeze.get("model_identity"), str)
            or len(freeze["model_identity"]) > 160
            or freeze.get("requested_backend") not in {"mlx", "ane", "rule_only"}):
        raise EvaluationError("model identity and backend must be separately declared")
    if type(freeze.get("case_count")) is not int or not 1 <= freeze["case_count"] <= MAX_CASES:
        raise EvaluationError("invalid frozen case count")
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for name, expected, actual in (
        ("dataset", freeze.get("dataset_sha256"), hashlib.sha256(data).hexdigest()),
        ("protocol", freeze.get("protocol_sha256"), hashlib.sha256(protocol.read_bytes()).hexdigest()),
        ("evaluator", freeze.get("evaluator_sha256"), code_sha),
    ):
        if not isinstance(expected, str) or not HEX64.fullmatch(expected) or expected != actual:
            raise EvaluationError(f"{name} freeze digest mismatch")
    rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    if len(rows) != freeze["case_count"]:
        raise EvaluationError("frozen case count mismatch")
    report = evaluate_rows(rows)
    report["freeze"] = dict(freeze)
    report["case_count"] = len(rows)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Audited Phase 8.3 offline paired-policy replay")
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--protocol", type=Path, default=Path("docs/PHASE8_3_EVALUATION_PROTOCOL.md"))
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = evaluate_file(args.dataset, args.manifest, args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"cases": report["case_count"], "groups": list(report["groups"]),
                      "real_agent_savings": "NOT_MEASURED"}, indent=2))


if __name__ == "__main__":
    main()
