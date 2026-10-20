#!/usr/bin/env python3
"""Preregistered Shadow-only 80-case local Laya replay.

With a model, this runner requires the exact case set, label oracle, protocol,
runner and operational policy sources already sealed by an ancestor Git commit.
No task actions, paid Providers, real Agent, downloads or Active authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.completion.phase8b_contract import expected_completion_hard_rule
from benchmarks.decision_value.capture import CompletionProbe, digest, opportunity
from benchmarks.decision_value.evaluate import evaluate_rows
from benchmarks.decision_value.holdout_v1.build_frozen import SCHEMA as CASE_SCHEMA
from benchmarks.retry.evaluate import _InferenceProbe, is_unsafe_to_retry, make_engine
from local_system_one.workflows.completion_gate import CompletionGate, CompletionGateRequest
from local_system_one.workflows.retry_escalation_gate import RetryEscalationGate, RetryEscalationRequest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CASES = HERE / "new_frozen_holdout_v1.jsonl"
FREEZE = HERE / "new_frozen_holdout_v1.freeze.json"
PROTOCOL = ROOT / "docs/PHASE8_3_NEW_HOLDOUT_PROTOCOL.md"
MODEL_REVISION = "f9ab0b228f0fc0f14d873dbc99038f135c2da1b2"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
CODE_TO_FREEZE = [
    "local_system_one/workflows/completion_gate.py",
    "local_system_one/workflows/retry_escalation_gate.py",
    "local_system_one/decision_opportunity.py",
    "benchmarks/decision_value/evaluate.py",
    "benchmarks/decision_value/capture.py",
    "benchmarks/completion/phase8b_contract.py",
    "benchmarks/retry/evaluate.py",
]


class HoldoutError(ValueError):
    """Frozen evidence or requested replay does not meet the declared protocol."""


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def check_freeze(commit: str) -> dict:
    if not isinstance(commit, str) or not SHA40.fullmatch(commit):
        raise HoldoutError("supply exact 40-character preregistration Git commit")
    try:
        git("merge-base", "--is-ancestor", commit, "HEAD")
    except subprocess.CalledProcessError as exc:
        raise HoldoutError("freeze commit is not an ancestor of current HEAD") from exc
    f = json.loads(FREEZE.read_text(encoding="utf-8"))
    keys = {"schema", "case_count", "split", "model_revision", "labels_origin",
            "native_outcomes", "paid_provider_requests", "hashes", "baseline_sha"}
    if not isinstance(f, dict) or set(f) != keys or (
        f.get("schema") != "local-system-one/preregistered-holdout-freeze-v1"
        or f.get("case_count") != 80 or f.get("split") != "frozen_holdout"
        or f.get("model_revision") != MODEL_REVISION
        or f.get("labels_origin") != "human-authored-synthetic-before-inference"
        or f.get("native_outcomes") != "NOT_MEASURED"
        or f.get("paid_provider_requests") != 0
        or not isinstance(f.get("baseline_sha"), str)
        or not SHA40.fullmatch(f["baseline_sha"])
    ):
        raise HoldoutError("unsupported or contradictory preregistration manifest")
    expect = {
        CASES.relative_to(ROOT).as_posix(),
        FREEZE.relative_to(ROOT).as_posix(),
        PROTOCOL.relative_to(ROOT).as_posix(),
        (HERE / "build_frozen.py").relative_to(ROOT).as_posix(),
        (HERE / "replay.py").relative_to(ROOT).as_posix(),
        *CODE_TO_FREEZE,
    }
    if not isinstance(f.get("hashes"), dict) or set(f["hashes"]) != (expect - {FREEZE.relative_to(ROOT).as_posix()}):
        raise HoldoutError("manifest must lock all prereg inputs AND production policy source")
    for name in sorted(f["hashes"]):
        expected_sha = f["hashes"][name]
        if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise HoldoutError("malformed code/data/protocol checksum")
        try:
            archived = git("show", f"{commit}:{name}")
        except subprocess.CalledProcessError as exc:
            raise HoldoutError("source missing from claimed pre-inference Git commit") from exc
        current = (ROOT / name).read_bytes()
        if hashlib.sha256(archived).hexdigest() != expected_sha or hashlib.sha256(current).hexdigest() != expected_sha:
            raise HoldoutError(f"frozen source has changed: {name}")
    try:
        frozen_manifest = git("show", f"{commit}:{FREEZE.relative_to(ROOT).as_posix()}")
    except subprocess.CalledProcessError as exc:
        raise HoldoutError("freeze manifest absent from pre-inference commit") from exc
    if frozen_manifest != FREEZE.read_bytes():
        raise HoldoutError("freeze manifest changed after Git registration")
    return f


def read_cases() -> list[dict]:
    cases = [json.loads(t) for t in CASES.read_text(encoding="utf-8").splitlines() if t.strip()]
    if len(cases) != 80 or len({r.get("id") for r in cases}) != 80:
        raise HoldoutError("missing or duplicate frozen cases")
    for r in cases:
        if set(r) != {"schema", "id", "family", "gate", "source", "split", "input", "gold"} or (
            r.get("schema") != CASE_SCHEMA or r.get("split") != "frozen_holdout"
            or r.get("input", {}).get("request_id") != r.get("id")
        ):
            raise HoldoutError("invalid case structure/identity")
        if r["gate"] == "completion" and r["source"] == "synthetic":
            CompletionGateRequest.from_payload(r["input"])
        elif r["gate"] == "retry_escalation" and r["source"] == "fault_injection":
            RetryEscalationRequest.from_payload(r["input"])
        else:
            raise HoldoutError("invalid source/Gate partition")
        gold = r["gold"]
        if set(gold) != {"oracle", "basis", "acceptable", "preferred"} or (
            not isinstance(gold["acceptable"], list) or
            gold["preferred"] not in gold["acceptable"]
        ):
            raise HoldoutError("missing preregistered independent editorial label")
        if gold["oracle"] != ("fault_oracle" if r["source"] == "fault_injection" else "synthetic_editorial"):
            raise HoldoutError("gold provenance inconsistent with synthetic source")
    return cases


def to_row(c: dict, *, b: str, final: str, raw: str | None, decision_source: str,
           backend: str, attempted: bool, completed: bool, latency: float | None,
           opp: dict, fallback: str | None = None) -> dict:
    # Only neutral case input is provided to a model. Model sees neither
    # gold nor family nor the oracle basis.
    input_digest = digest({k:v for k,v in c["input"].items() if k != "request_id"})
    forbidden = (is_unsafe_to_retry({"payload": c["input"]})
                 if c["gate"] == "retry_escalation" else False)
    invalid_output = attempted and completed and raw is None
    return {
        "schema": "local-system-one/decision-value-case-v1",
        "case_id": c["id"], "gate": c["gate"], "source": c["source"], "split": c["split"],
        "standardized_input_sha256": input_digest,
        "gold": {k:c["gold"][k] for k in ("acceptable","preferred","oracle")},
        "opportunity": opp, "rule_only": {"decision": b},
        "rules_model": {
            "guarded_decision": final, "raw_model_decision": raw,
            "decision_source": decision_source, "backend": backend,
            "model_invoked": attempted, "model_completed": completed,
            "safety_override": bool(attempted and completed and raw is not None and raw != final),
            "model_latency_ms": round(latency,3) if latency is not None else None,
            "failure_fallback": fallback, "model_output_invalid": invalid_output,
        },
        "native": {
            "decision": None, "decision_independently_adjudicated": False,
            "task_success": None, "task_outcome_independently_verified": False,
            "provider_attempts": None,
        },
        "safety": {"retry_forbidden_by_policy": forbidden},
    }


def replay(cases: list[dict], engine: Any = None) -> list[dict]:
    rows = []
    for c in cases:
        payload = c["input"]  # Never pass c["gold"] or c["family"] to the engine.
        if c["gate"] == "completion":
            req = CompletionGateRequest.from_payload(payload)
            hard = expected_completion_hard_rule(req.execution_state)
            forced = hard[0] if hard else None
            b = forced or "verify"
            opp = opportunity("completion", "turn_end", forced,
                              ["complete", "continue", "verify"])
            if forced is None and engine is not None:
                probe = CompletionProbe(engine)
                result = CompletionGate(probe).decide(req)
                attempted, completed = probe.attempted, probe.completed
                raw = probe.response.get("decision") if probe.response is not None else None
                final, source = result["decision"], result["decision_source"]
                backend, latency = probe.backend if completed else "unknown", probe.elapsed_ms
                fallback = "completion_fail_open_continue" if attempted and not completed else None
            else:
                attempted = completed = False
                raw = latency = fallback = None
                final = b
                source, backend = "rule", "rule"
        else:
            req = RetryEscalationRequest.from_payload(payload)
            gate = RetryEscalationGate()
            forced, _, allowed = gate._resolve_rules(req)
            b = gate.decide(req)["guarded_decision"]
            opp = opportunity("retry_escalation", "on_error", forced, allowed,
                              retry_safe="retry_same" in allowed,
                              escalation_safe="escalate_model" in allowed)
            if forced is None and engine is not None:
                probe = _InferenceProbe(engine)
                result = RetryEscalationGate(probe).decide(req)
                attempted, completed = probe.attempts > 0, probe.completed > 0
                raw = result.get("raw_model_decision")
                final, source = result["guarded_decision"], result["decision_source"]
                backend, latency = probe.last_backend if completed else "unknown", probe.last_latency_ms
                fallback = ("retry_rule_fallback" if attempted and
                            (not completed or raw is None) else None)
            else:
                attempted = completed = False
                raw = latency = fallback = None
                final = b
                source, backend = "rule", "rule"
        rows.append(to_row(c, b=b, final=final, raw=raw,
                           decision_source=source, backend=backend or "unknown",
                           attempted=attempted, completed=completed, latency=latency,
                           opp=opp, fallback=fallback))
    evaluate_rows(rows)
    return rows


def discordance(rows: list[dict]) -> dict:
    counts = {"both_correct":0,"rule_only_correct":0,"model_only_correct":0,"neither_correct":0}
    for r in rows:
        b = r["rule_only"]["decision"] in r["gold"]["acceptable"]
        c = r["rules_model"]["guarded_decision"] in r["gold"]["acceptable"]
        key = ("both_correct" if b and c else
               "rule_only_correct" if b else
               "model_only_correct" if c else "neither_correct")
        counts[key]+=1
    return {"n":len(rows), **counts,
            "additional_correct_choices": counts["model_only_correct"]-counts["rule_only_correct"]}


def main() -> None:
    p=argparse.ArgumentParser(description="Preregistered offline Laya replay, never Active")
    p.add_argument("--freeze-commit", required=True)
    p.add_argument("--source", type=Path, required=True,
                   help="pinned Laya local snapshot directory, not remote alias")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args=p.parse_args()
    frozen = check_freeze(args.freeze_commit)  # MUST precede make_engine()
    model_dir = args.source.expanduser().resolve()
    if (model_dir.name != MODEL_REVISION or not model_dir.is_dir()
        or not (model_dir/"rl_agent_config.json").is_file()):
        raise HoldoutError("model must be the pinned locally cached Laya snapshot; no download")
    cases=read_cases()
    engine=make_engine(str(model_dir),None)
    rows=replay(cases,engine)
    report=evaluate_rows(rows)
    report.update({
        "scope":"newly authored, preregistered synthetic/fault-injection pilot",
        "experiment":"phase8_3_new_frozen_holdout_v1",
        "freeze_git_commit":args.freeze_commit,
        "freeze_manifest_sha256":digest_file(FREEZE),
        "dataset_sha256":frozen["hashes"][CASES.relative_to(ROOT).as_posix()],
        "model_revision":MODEL_REVISION,
        "backend_observed":"mlx",
        "paid_provider_requests":0,
        "native_real_stepfun_validation":"NOT_RUN",
        "independent_real_agent_outcome":"NOT_MEASURED",
        "oracle_external_independence":"NOT_ESTABLISHED",
        "model_invoked_count":sum(r["rules_model"]["model_invoked"] for r in rows),
        "model_completed_count":sum(r["rules_model"]["model_completed"] for r in rows),
        "discordance": {
            key:discordance([r for r in rows if (
                r["gate"],r["source"],r["split"]) == (
                g["gate"],g["source"],g["split"])])
            for key,g in report["groups"].items()
        },
        "fixed_case_count":80,
        "all_80_cases_retained":True,
    })
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in rows),encoding="utf-8")
    args.report.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "frozen_commit":args.freeze_commit,
        "cases":80,"model_attempts":report["model_invoked_count"],
        "model_completed":report["model_completed_count"],
        "groups":{k:{"rule":v["rule_only_quality"]["acceptable_accuracy"],
                     "laya":v["rules_model_quality"]["acceptable_accuracy"],
                     "model_attempts":v["model_attempted"]}
                  for k,v in report["groups"].items()},
        "main_provider_attempts":0,
    },indent=2))


if __name__=="__main__":
    main()
