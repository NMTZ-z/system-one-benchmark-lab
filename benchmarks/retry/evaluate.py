"""Independent Phase 8C public-synthetic Rule vs Laya benchmark (shadow only).

Native Agent baseline A must be obtained by separate paired Agent experiments;
this script compares B (deterministic fallback) vs C (guarded Laya suggestions).
It neither performs retries nor measures saved API tokens or tool calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from local_system_one.workflows.retry_escalation_gate import (
    RetryEscalationGate, RetryEscalationRequest, DECISIONS,
)

CORPUS_DIR = Path(__file__).resolve().parent
FROZEN_SHA256 = {
    "calibration": "994d8a9e57a3e1668e3dade5692387228b28df1ac3ebb59c548dea966f376e26",
    "holdout": "733953cd214d353becee7fb026eaba31b1b25c148f2fe170de42b00721d60c1e",
    "adversarial": "a92c74d16527e06662bb5f9d98100308e6f1879b4a52fdea2120ab24da8bff77",
}


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    a = 1 + z*z/n
    center = (p + z*z/(2*n)) / a
    spread = z/a * math.sqrt((p*(1-p)+z*z/(4*n))/n)
    return [round(max(0, center-spread),6), round(min(1,center+spread),6)]


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = (len(values)-1)*p
    lo, hi = int(index), min(int(index)+1,len(values)-1)
    return round(sorted_values[lo]+(sorted_values[hi]-sorted_values[lo])*(index-lo),3)


def is_unsafe_to_retry(case: dict[str, Any]) -> bool:
    """Count *all* cases where the Runtime's hard policy forbids retry_same.

    The denominator follows the same typed request validation and candidate
    filtering as the production gate, not a second hand-maintained predicate
    or the model/gold label. This includes untrusted metadata, too many
    repeated failures and non-transient errors, as well as explicit hazards.
    "Unsafe" here means *policy-prohibited*, not observed real-world harm.
    Invalid typed requests cannot receive retry authority either.
    """
    try:
        req = RetryEscalationRequest.from_payload(case["payload"])
    except (TypeError, ValueError, KeyError):
        return True
    forced, _reason, allowed = RetryEscalationGate()._resolve_rules(req)
    return forced != "retry_same" if forced is not None else "retry_same" not in allowed


class _InferenceProbe:
    """Observe actual Engine calls independently of guarded decision_source.

    The gate may safely replace a completed or malformed model answer with a
    rule. That must not erase the already incurred inference call/latency.
    This wrapper is benchmark-only; it does not change the Runtime response
    schema, execute native Agent actions or intercept tool requests.
    """

    def __init__(self, engine: Any):
        self._engine = engine
        self.attempts = 0
        self.completed = 0
        self.last_latency_ms: float | None = None
        self.last_backend: str | None = None

    @property
    def metrics(self):
        # Preserve the real Engine's single-request error accounting behavior.
        return self._engine.metrics

    def decide(self, request: Any) -> Any:
        self.attempts += 1
        self.last_backend = None
        start = time.perf_counter()
        try:
            result = self._engine.decide(request)
            self.completed += 1
            if isinstance(result, dict) and isinstance(result.get("backend"), str):
                self.last_backend = result["backend"]
            return result
        finally:
            self.last_latency_ms = (time.perf_counter() - start) * 1000


def _inference_attempted(row: dict[str, Any]) -> bool:
    # evaluate() supplies an explicit call observation. The legacy fallback
    # supports hand-built/older rows but cannot infer a failed invisible call.
    return bool(row.get(
        "model_inference_attempted",
        row.get("decision_source") == "model" or row.get("raw_model_decision") is not None,
    ))


def _inference_completed(row: dict[str, Any]) -> bool:
    return bool(row.get(
        "model_inference_completed",
        row.get("decision_source") == "model" or row.get("raw_model_decision") is not None,
    ))


def policy_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    matrix = {
        gold:{pred:sum(x["gold"]==gold and x["decision"]==pred for x in rows)
              for pred in DECISIONS}
        for gold in DECISIONS
    }
    scores={}
    for label in DECISIONS:
        tp=matrix[label][label]
        total_gold=sum(matrix[label].values())
        total_pred=sum(matrix[gold][label] for gold in DECISIONS)
        precision=tp/total_pred if total_pred else 0
        recall=tp/total_gold if total_gold else 0
        f1=(2*precision*recall/(precision+recall)) if precision+recall else 0
        scores[label]={
            "precision":round(precision,4),
            "recall":round(recall,4),
            "f1":round(f1,4),
            "count":total_gold,
        }
    unsafe = [x for x in rows if is_unsafe_to_retry(x)]
    unsafe_wrong=sum(x["decision"]=="retry_same" for x in unsafe)
    verify_required=[x for x in rows if x["gold"]=="verify_state"]
    missed=sum(x["decision"] in ("retry_same","try_alternative","escalate_model") for x in verify_required)
    unnecessary=sum(x["decision"]=="escalate_model" and x["gold"]!="escalate_model" for x in rows)
    attempts=[x["latency_ms"] for x in rows]
    # Track real inference work, not the *guarded* final decision label.
    # A safety override or malformed response can have decision_source=rule
    # even though Engine.decide() actually ran (or failed).
    inferred=[x for x in rows if _inference_attempted(x)]
    model_latencies=[x["latency_ms"] for x in inferred]
    engine_latencies=[
        x["model_inference_latency_ms"] for x in inferred
        if isinstance(x.get("model_inference_latency_ms"), (int, float))
        and not isinstance(x["model_inference_latency_ms"], bool)
    ]
    correct=sum(x["gold"]==x["decision"] for x in rows)
    return {
        "n":n, "accuracy":round(correct/n,4) if n else None,
        "macro_f1":round(statistics.mean(z["f1"] for z in scores.values()),4),
        "per_label":scores, "confusion":matrix,
        "unsafe_retry_rate": {
            "count":unsafe_wrong, "denominator":len(unsafe),
            "rate":round(unsafe_wrong/len(unsafe),4) if unsafe else None,
            "wilson95":wilson(unsafe_wrong,len(unsafe)),
        },
        "missed_verification_rate": {
            "count":missed, "denominator":len(verify_required),
            "rate":round(missed/len(verify_required),4) if verify_required else None,
            "wilson95":wilson(missed,len(verify_required)),
        },
        "unnecessary_escalation_rate":{
            "count":unnecessary,"denominator":n,
            "rate":round(unnecessary/n,4) if n else None,
        },
        "model_activated_count":len(inferred),
        "model_inference_completed_count":sum(_inference_completed(x) for x in inferred),
        "model_inference_failed_count":sum(not _inference_completed(x) for x in inferred),
        "p50_wall_ms":percentile(attempts,0.5),
        "p95_wall_ms":percentile(attempts,0.95),
        "p50_model_path_ms":percentile(model_latencies,0.5),
        "p95_model_path_ms":percentile(model_latencies,0.95),
        "p50_engine_call_ms":percentile(engine_latencies,0.5),
        "p95_engine_call_ms":percentile(engine_latencies,0.95),
        # Backend on guarded output may be 'rule' after a genuine MLX call.
        # Keep this distinct from the actual inference backend.
        "backend_count":dict(Counter(x["backend"] for x in rows)),
        "inference_backend_count":dict(Counter(
            x.get("model_inference_backend") or "unknown" for x in inferred
        )),
        "safety_override_count":sum(bool(x["safety_override_reason"]) for x in rows),
    }


def load_split(split: str) -> list[dict]:
    path=CORPUS_DIR/f"{split}.jsonl"
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != FROZEN_SHA256[split]:
        raise ValueError(f"{split} freeze SHA mismatch")
    rows=[json.loads(x) for x in path.read_text().splitlines()]
    if len(rows)!=30 or any(row["split"]!=split or row["source"]!="synthetic" for row in rows):
        raise ValueError("invalid corpus provenance/split")
    if len({x["case_id"] for x in rows})!=len(rows):
        raise ValueError("duplicate synthetic case")
    return rows


def make_engine(source: str, ane_package: str | None):
    from local_system_one.engine import DecisionEngine
    from local_system_one.health import ANEHealthGate
    from local_system_one.router import DecisionRouter, RouterConfig
    from local_system_one.runtime import MLXRuntime, ANERuntime
    mlx=MLXRuntime(source)
    ane=ANERuntime(source,Path(ane_package),length=512) if ane_package else None
    return DecisionEngine(
        mlx=mlx,ane=ane,
        router=DecisionRouter(RouterConfig()),
        health=ANEHealthGate(available=ane is not None),
    )


def evaluate(rows: list[dict], engine=None, backend="mlx") -> list[dict]:
    # Capture inference work at the call boundary. A guarded fallback can
    # erase the model's *decision*, never its actual compute cost.
    probe = _InferenceProbe(engine) if engine is not None else None
    gate=RetryEscalationGate(probe)
    output=[]
    for row in rows:
        payload=dict(row["payload"])
        payload["backend"] = backend if engine is not None else "auto"
        request=RetryEscalationRequest.from_payload(payload)
        before_calls = probe.attempts if probe is not None else 0
        before_completed = probe.completed if probe is not None else 0
        started=time.perf_counter()
        decision=gate.decide(request)
        attempted = probe is not None and probe.attempts > before_calls
        completed = attempted and probe.completed > before_completed
        output.append({
            "case_id":row["case_id"],"gold":row["gold"],
            "decision":decision["guarded_decision"],
            "raw_model_decision":decision.get("raw_model_decision"),
            "decision_source":decision["decision_source"],
            "safety_override_reason":decision["safety_override_reason"],
            "backend":decision["backend"],
            "latency_ms":round((time.perf_counter()-started)*1000,3),
            "model_inference_attempted":attempted,
            "model_inference_completed":completed,
            "model_inference_backend":probe.last_backend if attempted else None,
            "model_inference_latency_ms":(
                round(probe.last_latency_ms,3)
                if attempted and probe.last_latency_ms is not None else None
            ),
            "payload":payload,
        })
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",help="locally pinned typed-decisions model directory")
    parser.add_argument("--ane-package",help="isolated CoreML model.mlpackage")
    parser.add_argument("--output",required=True,help="aggregate-only public report JSON")
    args=parser.parse_args()
    cases={split:load_split(split) for split in FROZEN_SHA256}
    result={
        "scope":"phase8c_synthetic_shadow",
        "corpus_freeze_sha256":FROZEN_SHA256,
        "sample_sources":{"synthetic":90,"real":0},
        "native_agent_baseline":"NOT_MEASURED",
        "notes":[
            "Labels are synthetic editorial assumptions and not independent real outcomes.",
            "Strictly passive model/rule calls; no actual retries, API token savings, or agent execution.",
            "Experimental probabilities are uncalibrated model scores, not guaranteed posteriors.",
        ],
        "splits":{},
    }
    engine=make_engine(args.source,args.ane_package) if args.source else None
    for split,rows in cases.items():
        baseline=evaluate(rows)
        entry={
            "source":"synthetic",
            "rule_only":policy_metrics(baseline),
            "engine":None if engine is None else "laya_421m",
        }
        if engine is not None:
            model=evaluate(rows,engine,"mlx")
            entry["rules_laya_mlx"]=policy_metrics(model)
            entry["incremental_accuracy_pct_points"]=round(
                100*(entry["rules_laya_mlx"]["accuracy"]-entry["rule_only"]["accuracy"]),2,
            )
            if args.ane_package:
                ane=evaluate(rows,engine,"ane")
                entry["rules_laya_ane"]=policy_metrics(ane)
                # Pair actual inference observations. A safety override
                # must not make completed backend work disappear from coverage.
                pairs=[(m,a) for m,a in zip(model,ane)
                       if m["model_inference_attempted"] and a["model_inference_attempted"]]
                valid=[(m,a) for m,a in pairs
                       if (a["model_inference_backend"]=="ane"
                           and m["raw_model_decision"] is not None
                           and a["raw_model_decision"] is not None)]
                entry["ane_mlx_comparison"]={
                    "model_eligible_pairs":len(pairs),
                    "ane_actual_pairs":len(valid),
                    "raw_agreement_count":sum(m["raw_model_decision"]==a["raw_model_decision"] for m,a in valid),
                    "final_agreement_count":sum(m["decision"]==a["decision"] for m,a in valid),
                    "fallback_to_mlx_pairs":len(pairs)-len(valid),
                }
        result["splits"][split]=entry
    output=Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        split:{"rule":val["rule_only"]["accuracy"],
               "mlx":val.get("rules_laya_mlx",{}).get("accuracy")}
        for split,val in result["splits"].items()
    }))
    print("Aggregate-only benchmark written.")


if __name__=="__main__":
    main()
