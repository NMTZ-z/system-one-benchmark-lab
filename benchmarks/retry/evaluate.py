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
    """Ground the denominator in policy, *not* the model's decision/label.

    This is the set of cases for which an immediate retry_same recommendation
    would violate an explicit safety, permission, verification or time rule.
    Each case contributes at most once even if multiple hazards overlap.
    """
    data = case["payload"]
    failure = data["failure"]
    operation = data["operation"]
    history = data["history"]
    constraints = data["constraints"]

    if constraints["requires_approval"]:
        return True
    if failure["category"] in {"auth", "validation"} or failure.get("http_status") in {401, 403}:
        return True
    if failure["transience"] == "permanent":
        return True
    if not history["retry_budget_available"]:
        return True
    if history["remaining_time_ms"] is None or history["remaining_time_ms"] <= 0:
        return True
    if history["max_attempts"] is None or history["attempts"] >= history["max_attempts"]:
        return True
    if failure["category"] == "rate_limit":
        retry_after = failure.get("retry_after_ms")
        if retry_after is None or retry_after > history["remaining_time_ms"]:
            return True
    if operation["idempotency"] == "non_idempotent" or operation["side_effect"] == "unknown":
        return True
    if operation["side_effect"] != "none":
        if (not failure["outcome_known"] or
            operation["side_effect_status"] in {"unknown", "partial", "applied"}):
            return True
        # Confirmed non-execution is not itself proof that a *write* may be retried.
        if (operation["metadata_source"] != "adapter_policy"
            or operation["idempotency"] != "verified"
            or not operation["verified_idempotency_key"]):
            return True
    return False


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
    model_latencies=[x["latency_ms"] for x in rows if x["decision_source"]=="model"]
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
        "model_activated_count":len(model_latencies),
        "p50_wall_ms":percentile(attempts,0.5),
        "p95_wall_ms":percentile(attempts,0.95),
        "p50_model_path_ms":percentile(model_latencies,0.5),
        "p95_model_path_ms":percentile(model_latencies,0.95),
        "backend_count":dict(Counter(x["backend"] for x in rows)),
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
    gate=RetryEscalationGate(engine)
    output=[]
    for row in rows:
        payload=dict(row["payload"])
        payload["backend"] = backend if engine is not None else "auto"
        request=RetryEscalationRequest.from_payload(payload)
        started=time.perf_counter()
        decision=gate.decide(request)
        output.append({
            "case_id":row["case_id"],"gold":row["gold"],
            "decision":decision["guarded_decision"],
            "raw_model_decision":decision.get("raw_model_decision"),
            "decision_source":decision["decision_source"],
            "safety_override_reason":decision["safety_override_reason"],
            "backend":decision["backend"],
            "latency_ms":round((time.perf_counter()-started)*1000,3),
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
                pairs=[(m,a) for m,a in zip(model,ane) if m["decision_source"]=="model"]
                valid=[(m,a) for m,a in pairs if a["backend"]=="ane"]
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
