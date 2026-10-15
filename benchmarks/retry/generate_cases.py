"""Frozen, PUBLIC synthetic Retry decision cases. Never use private Agent traces.

Corpus labels are hand-authored hypotheses, not independently adjudicated real
outcomes; holdout family names are disjoint, but patterns remain correlated.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
LABELS = ("retry_same", "try_alternative", "escalate_model", "verify_state", "ask_user", "abort")
SPLITS = ("calibration", "holdout", "adversarial")
CATEGORIES = ("network", "timeout", "server_error", "tool_error", "test_failure", "logic_failure")

def make_case(split: str, gold: str, index: int) -> dict:
    if split not in SPLITS or gold not in LABELS:
        raise ValueError("unknown dataset category")
    offset = SPLITS.index(split)
    failure = {"category": "timeout", "transience": "transient", "outcome_known": True}
    operation = {
        "type": "read", "side_effect": "none", "idempotency": "verified",
        "side_effect_status": "none", "verified_idempotency_key": False,
        "reversibility": "yes", "metadata_source": "adapter_policy",
    }
    history = {
        "attempts": 1, "max_attempts": 4, "repeated_failures": 0,
        "remaining_time_ms": 20000, "retry_budget_available": True,
    }
    constraints = {
        "requires_approval": False, "escalation_allowed": False,
        "escalation_budget_available": False, "alternative_available": False,
    }
    scenario = f"{split}-synthetic-{gold}-variant-{index + 1}"

    if gold == "verify_state":
        operation.update({
            "type": ("pr_create", "git_push", "local_file", "remote_api", "write")[(index+offset)%5],
            "side_effect": "external" if index%2 else "write",
            "idempotency": "unknown", "side_effect_status": "unknown",
            "reversibility": "unknown",
        })
        failure.update(category=("timeout","network","partial_success","tool_error","unknown")[(index+offset)%5],
                       transience="unknown", outcome_known=False)
        if index == 3:
            operation["side_effect_status"] = "partial"
        scenario += "-unconfirmed-remote-mutation"

    elif gold == "ask_user":
        if index % 5 in (0,1):
            failure.update(category="auth",transience="permanent",
                           http_status=401 if index%5==0 else 403)
        elif index%5==2:
            constraints["requires_approval"]=True
        elif index%5==3:
            failure.update(category="validation", transience="permanent")
        else:
            history["retry_budget_available"]=False
            history["remaining_time_ms"]=None
            history["max_attempts"]=None
        scenario += "-approval-or-credential"

    elif gold == "abort":
        if index%5 in (0,1):
            history["attempts"] = 4
            history["max_attempts"] = 4
        elif index%5 == 2:
            operation.update({
                "type":"remote_api", "side_effect":"external",
                "idempotency":"unknown", "side_effect_status":"applied",
            })
        elif index%5 == 3:
            failure.update(category="tool_error",transience="permanent")
        else:
            history["remaining_time_ms"]=0
        scenario += "-budget-exhausted-or-already-applied"

    elif gold == "retry_same":
        failure.update(category=("timeout","network","server_error")[(index+offset)%3])
        history["attempts"]=1
        history["max_attempts"]=4
        # For these synthetic cases the approved preference is retry once under
        # caller-controlled delay; the model is not granted actual execution rights.
        scenario += "-known-safe-retry-eligible"

    elif gold == "try_alternative":
        failure.update(category=("network","server_error","timeout")[(index+offset)%3])
        history["repeated_failures"]=2+index%2
        history["attempts"]=2
        constraints["alternative_available"]=True
        scenario += "-repeated-read-failures-available-alternative"

    elif gold == "escalate_model":
        failure.update(
            category=("tool_error", "test_failure", "logic_failure")[(index+offset)%3],
            transience="unknown",
        )
        constraints["escalation_allowed"]=True
        constraints["escalation_budget_available"]=True
        history["attempts"]=2
        scenario += "-reasoning-repair-allowed-by-budget"

    if split == "adversarial":
        # Structured stress, not misleading text: stronger budget and
        # verified/nonverified evidence in tension; hard rules still dominate.
        if gold == "verify_state":
            history["retry_budget_available"]=True
            history["max_attempts"]=10
        if gold == "ask_user" and index%5==4:
            history["retry_budget_available"]=False
        if gold == "abort" and index%5==2:
            constraints["alternative_available"]=True
        if gold == "retry_same" and index%5==4:
            constraints["alternative_available"]=True
        if gold == "escalate_model" and index%5==4:
            constraints["alternative_available"]=True
        scenario += "-adversarial-structured-confound"

    payload = {
        "failure": failure, "operation": operation,
        "history": history, "constraints": constraints,
        "request_id": f"synthetic-{split}-{gold}-{index:02d}",
    }
    return {
        "case_id": f"{split}-{gold}-{index:02d}",
        "split":split,"source":"synthetic",
        "scenario":scenario, "gold":gold, "payload":payload,
    }


def main() -> None:
    for split in SPLITS:
        rows = [
            make_case(split, gold, index)
            for gold in LABELS for index in range(5)
        ]
        file = ROOT / f"{split}.jsonl"
        file.write_text(
            "\n".join(json.dumps(row,sort_keys=True,separators=(",",":")) for row in rows)+"\n",
            encoding="utf-8",
        )
        print(f"{split}: {len(rows)} public synthetic cases -> {file.name}")


if __name__ == "__main__":
    main()
