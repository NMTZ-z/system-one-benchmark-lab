#!/usr/bin/env python3
"""Capture privacy-safe *offline* synthetic/public-reconstruction Gate replay.

No Agent, paid Provider, retry, stop, model switch or native E2E. The capture
format stores digests, labels and locally measured model calls, never task text.
The independently frozen source corpi remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from benchmarks.completion.phase8b_contract import expected_completion_hard_rule
from benchmarks.completion.phase8b_offline import rule_only as completion_rule_only
from benchmarks.retry.evaluate import (
    FROZEN_SHA256, evaluate as retry_evaluate, is_unsafe_to_retry,
    load_split, make_engine,
)
from local_system_one.workflows.completion_gate import CompletionGate, CompletionGateRequest
from local_system_one.workflows.retry_escalation_gate import (
    RetryEscalationGate, RetryEscalationRequest,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_SCHEMA = "local-system-one/decision-value-case-v1"
OPP_SCHEMA = "local-system-one/opportunity-v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def opportunity(gate: str, stage: str, rule: str | None, labels: list[str],
                *, retry_safe: bool = False, escalation_safe: bool = False) -> dict:
    # Only already-validated public fixture input and existing deterministic
    # policy objects reach this adapter. This is STRUCTURAL SYNTHETIC evidence,
    # not a claim that a real Agent task outcome was independently checked.
    return {
        "schema": OPP_SCHEMA, "gate": gate, "observation_stage": stage,
        "evidence": {
            "source": "independently_verified", "status": "verified",
            "capabilities": {}, "required_capabilities": [], "verified_conditions": [],
        },
        "candidates": {
            "labels": labels, "bounded": True, "stable": True,
            "guard_source": "adapter_policy",
        },
        "rule": {
            "resolved": rule is not None, "decision": rule,
            "source": "adapter_policy",
        },
        "constraints": {
            "requires_generation": False, "permission_verified": False,
            "side_effect_status": "unknown",
            "retry_policy_eligible": retry_safe,
            "escalation_policy_eligible": escalation_safe,
            "independent_verification_required": True,
        },
        "authority": {"mode": "shadow", "action_allowed": False},
    }


def make_row(*, case_id: str, gate: str, source: str, split: str,
             input_sha: str, gold: str, rule: str, opp: dict,
             final: str, raw: str | None, decision_source: str,
             backend: str, attempted: bool, completed: bool,
             latency: float | None, retry_forbidden: bool = False) -> dict:
    oracle = {"synthetic": "synthetic_editorial",
              "public_reconstruction": "reconstruction_editorial"}[source]
    # The Native Agent baseline is deliberately missing. Neither locally
    # generated model answers nor historical narrative are Native E2E proof.
    return {
        "schema": DATA_SCHEMA,
        "case_id": case_id, "gate": gate, "source": source, "split": split,
        "standardized_input_sha256": input_sha,
        "gold": {"acceptable": [gold], "preferred": gold, "oracle": oracle},
        "opportunity": opp,
        "rule_only": {"decision": rule},
        "rules_model": {
            "guarded_decision": final, "raw_model_decision": raw,
            "decision_source": decision_source, "backend": backend,
            "model_invoked": attempted, "model_completed": completed,
            "safety_override": completed and raw != final,
            "failure_fallback": (
                ("completion_fail_open_continue" if gate == "completion" else "retry_rule_fallback")
                if attempted and not completed else None
            ),
            "model_output_invalid": False,
            "model_latency_ms": round(latency, 3) if latency is not None else None,
        },
        "native": {
            "decision": None, "decision_independently_adjudicated": False,
            "task_success": None, "task_outcome_independently_verified": False,
            "provider_attempts": None,
        },
        "safety": {"retry_forbidden_by_policy": retry_forbidden},
    }


def replay_retry(engine) -> list[dict]:
    output = []
    for split in FROZEN_SHA256:
        rows = load_split(split)  # checks the previously frozen upstream SHA
        rule_rows = retry_evaluate(rows)
        model_rows = retry_evaluate(rows, engine, "mlx") if engine else rule_rows
        for case, b, c in zip(rows, rule_rows, model_rows, strict=True):
            req = RetryEscalationRequest.from_payload(case["payload"])
            forced, _reason, choices = RetryEscalationGate()._resolve_rules(req)
            attempted = bool(c["model_inference_attempted"])
            completed = bool(c["model_inference_completed"])
            raw = c.get("raw_model_decision")
            if attempted and not completed:
                # Never fill unknown inference with fabricated raw outcomes.
                raw = None
            output.append(make_row(
                case_id=case["case_id"], gate="retry_escalation", source="synthetic",
                split="historical_holdout" if split == "holdout" else split,
                input_sha=digest({k:v for k,v in case["payload"].items() if k != "request_id"}),
                gold=case["gold"], rule=b["decision"],
                opp=opportunity("retry_escalation", "on_error", forced, list(choices),
                    retry_safe="retry_same" in choices,
                    escalation_safe="escalate_model" in choices),
                final=c["decision"], raw=raw, decision_source=c["decision_source"],
                backend=(c["model_inference_backend"] or "unknown") if attempted else "rule",
                attempted=attempted, completed=completed,
                latency=c.get("model_inference_latency_ms"),
                retry_forbidden=is_unsafe_to_retry(case),
            ))
    return output


class CompletionProbe:
    def __init__(self, engine: Any):
        self._engine = engine
        self.metrics = engine.metrics
        self.health = engine.health
        self.attempted = False
        self.completed = False
        self.response = None
        self.backend = "unknown"
        self.elapsed_ms = None

    def decide(self, request):
        self.attempted = True
        started = time.perf_counter()
        try:
            self.response = self._engine.decide(request)
            self.completed = True
            self.backend = self.response.get("backend", "unknown")
            return self.response
        finally:
            self.elapsed_ms = (time.perf_counter()-started)*1000


def replay_completion(engine) -> list[dict]:
    path = ROOT / "benchmarks/completion/gold_v0.1.jsonl"
    source_bytes = path.read_bytes()
    items = [json.loads(x) for x in source_bytes.decode().splitlines() if x.strip()]
    # Existing public Phase8A gold, not an independent new or private blind set.
    seen = set()
    output = []
    for item in items:
        if item["id"] in seen:
            raise ValueError("duplicate frozen public completion case")
        seen.add(item["id"])
        state = item["execution_state"]
        hard = expected_completion_hard_rule(state)
        b = completion_rule_only({"deterministic_rule": hard[0] if hard else None}, state)
        probe = CompletionProbe(engine) if engine is not None else None
        if probe is not None:
            request = CompletionGateRequest.from_payload({
                "task": item["task"], "current_result": item["current_result"],
                "execution_state": state, "request_id": item["id"],
            })
            result = CompletionGate(probe).decide(request)
            final = result["decision"]
            raw = probe.response["decision"] if probe.response else None
            if probe.attempted and not probe.completed:
                raise RuntimeError("unqualified completion inference failure: capture blocked")
            backend = probe.backend if probe.attempted else "rule"
            attempted = probe.attempted
            completed = probe.completed
            latency = probe.elapsed_ms if attempted else None
            source = result["decision_source"]
        else:
            final, raw, backend, attempted, completed, latency, source = (
                b, None, "rule", False, False, None, "rule",
            )
        public_source = "synthetic" if item["source"] == "synthetic" else "public_reconstruction"
        output.append(make_row(
            case_id=item["id"], gate="completion", source=public_source,
            split="development",
            input_sha=digest({"task": item["task"], "current_result": item["current_result"],
                              "execution_state": state}),
            gold=item["label"], rule=b,
            opp=opportunity("completion", "turn_end", hard[0] if hard else None,
                            ["complete", "continue", "verify"]),
            final=final, raw=raw, decision_source=source, backend=backend,
            attempted=attempted, completed=completed, latency=latency,
        ))
    return output


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source", help="already-cached local Laya source; no paid Provider calls")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    engine = make_engine(args.source, None) if args.source else None
    cases = replay_retry(engine) + replay_completion(engine)
    from benchmarks.decision_value.evaluate import evaluate_rows
    evaluate_rows(cases)  # refuse inconsistent/unsafe captures before writing.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(c, sort_keys=True)+"\n" for c in cases),
                           encoding="utf-8")
    print(json.dumps({
        "cases": len(cases),
        "model_attempted": sum(c["rules_model"]["model_invoked"] for c in cases),
        "model_completed": sum(c["rules_model"]["model_completed"] for c in cases),
        "native_agent_e2e": "NOT_RUN", "paid_provider_requests": 0,
    }))


if __name__ == "__main__":
    main()
