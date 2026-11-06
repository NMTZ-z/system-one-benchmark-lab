#!/usr/bin/env python3
"""Read-only provenance-first intake of three historic real StepFun tasks.

No private ledger parse, Provider calls, prompts, credentials, hidden tasks,
new local inference or fabricated decision gold. Never pool source classes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HISTORIC_FILES = {
    "H1": ("phase8_3_h1_real_stepfun_partial.json", "d22db1cad7ede1acbda769f2362cd44ebb60806efbe5e5300edbc6f50735564a"),
    "H2": ("phase8_3_h2_real_stepfun_shadow.json", "0d6e55d8025cb0e602804262664bcc203f552830a2b74b0adfc4e464596785f1"),
    "H3": ("phase8_3_h3_real_stepfun_runtime_down.json", "2c4941d4ebd90e41193ff52c8d6d95adac728068ea73b933e212b26594128653"),
}


class RealIntakeBlocked(ValueError):
    """Source evidence cannot support the claimed real task/effect."""


def demand(ok: bool, reason: str) -> None:
    if not ok:
        raise RealIntakeBlocked(reason)


def bounded_json(path: Path) -> dict[str, Any]:
    demand(path.is_file() and not path.is_symlink(), "missing_public_original")
    demand(path.stat().st_size < 25000, "oversized_public_original")
    data=json.loads(path.read_text(encoding="utf-8"))
    demand(isinstance(data, dict), "malformed_public_original")
    return data


def historical_inputs(root: Path=ROOT) -> dict[str,dict]:
    results={}
    for case,(name,expected) in HISTORIC_FILES.items():
        path=root/"results/processed"/name
        demand(path.is_file() and not path.is_symlink(), "missing_or_symlinked_history")
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        demand(digest==expected, "historical_public_evidence_changed")
        results[case]=bounded_json(path)
    return results


def assess_historical_data(data: dict[str,dict]) -> dict[str,Any]:
    demand(type(data) is dict and set(data)==set(HISTORIC_FILES), "unexpected_real_evidence_sources")
    h1,h2,h3=(data[k] for k in ("H1","H2","H3"))
    task=h1.get("native_task",{}); physical=h1.get("physical_request_budget",{})
    demand(h1.get("schema")=="local-system-one/phase8_3-real-native-h1-evidence-v1" and
           h1.get("platform")=="hermes" and h1.get("system_one_mode")=="off" and
           h1.get("phase8_3_real_native_acceptance")=="BLOCKED_BUDGET_RECONCILIATION" and
           task.get("task_result")=="PASS_SCOPED" and
           all(task.get(k) is True for k in ("agent_final_matches_file","independent_tool_call_result_match",
                                                "native_agent_exit_success","original_file_bytes_verified")),
           "unverified_original_H1_native_task")
    demand(all(type(physical.get(k)) is int for k in ("attempted","attempted_unresolved","provider_responded","cap_global"))
           and physical["attempted"]==3 and physical["attempted_unresolved"]==1
           and physical["provider_responded"]==2 and physical["cap_global"]==24
           and physical.get("budget_integrity")=="BLOCKED" and
           h1.get("real_agent_savings")=="NOT_MEASURED", "H1_unknown_or_budget_mutated")
    n2=h2.get("h2_native",{}); m2=h2.get("h2_local_laya",{});b2=h2.get("h2_physical_provider",{})
    demand(h2.get("schema")=="local-system-one/phase8_3-real-h2-adjudicated-v1" and
           h2.get("platform")=="hermes" and h2.get("native_mode")=="shadow" and
           h2.get("h2_scoped_qualification")=="PASS_SCOPED" and
           n2.get("task_outcome")=="PASS_SCOPED" and n2.get("native_exit_code")==0 and
           all(n2.get(k) is True for k in ("tool_result_identity_verified","tool_result_matches_independent_file",
                                               "agent_final_matches_independent_file")),
           "unverified_original_H2_native_task")
    demand(m2.get("mlx_model_decision_observed")==2 and
           m2.get("strict_native_adapter_http_joined")==2 and
           m2.get("exact_causal_correlation")=="PASS_SCOPED" and
           m2.get("completion_HTTP_200")==2 and
           b2.get("h2_physical_attempts")==3 and b2.get("h2_provider_responses_HTTP_200")==3 and
           b2.get("h2_attempted_unresolved")==0 and b2.get("original_h1_physical_attempts")==3 and
           b2.get("historical_h1_unresolved")==1 and b2.get("global_physical_attempts_total")==6,
           "H2_model_or_budget_claim_conflicted")
    n3=h3.get("native_task",{});b3=h3.get("provider_physical",{});runtime=h3.get("shadow_runtime_down",{})
    demand(h3.get("schema")=="local-system-one/phase8_3-h3-real-native-adjudicated-v1" and
           h3.get("platform")=="hermes" and h3.get("native_mode")=="shadow" and
           h3.get("h3_scoped_qualification")=="PASS_SCOPED" and
           n3.get("outcome")=="PASS_SCOPED" and n3.get("agent_exit_code")==0 and
           all(n3.get(k) is True for k in ("one_native_read_file_and_result_identity","tool_bytes_match_original_file",
                                               "file_was_not_mutated","final_answer_matches_original_file")),
           "unverified_original_H3_native_task")
    demand(b3.get("previous_h1_requests")==3 and b3.get("previous_h2_requests")==3 and
           b3.get("H3_attempted")==2 and b3.get("H3_responded_HTTP_200")==2 and
           b3.get("H3_unresolved")==0 and b3.get("total_requests_reserved_so_far")==8 and
           b3.get("original_h1_unresolved")==1 and
           b3.get("H3_original_ledger_sha256")=="5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb" and
           runtime.get("native_adapter_http_exact_pairs")==2 and
           runtime.get("observed_completion_HTTP_503")==2 and
           runtime.get("adapter_failed_open_observations")==2 and
           runtime.get("active_action_allowed") is False,
           "H3_Provider_or_runtime_down_mutated")
    # Evidence is real Agent tasks; the published redacted aggregates lack
    # decision-level independently assigned gold. We *refuse* to construct
    # positive decision examples from task outcomes or final Agent messages.
    observations={
       "H1":{"source":"real_native_stepfun","scope":"off_read_only_success", "verified_task":True,
             "physical_attempts":3,"terminal_http_200":2,"unresolved_attempts":1,
             "local_decision_predictions":0,"independent_decision_gold":False},
       "H2":{"source":"real_native_stepfun","scope":"shadow_read_only_success", "verified_task":True,
             "physical_attempts":3,"terminal_http_200":3,"unresolved_attempts":0,
             "local_decision_predictions":2,"independent_decision_gold":False},
       "H3":{"source":"real_native_stepfun","scope":"runtime_down_read_only_success", "verified_task":True,
             "physical_attempts":2,"terminal_http_200":2,"unresolved_attempts":0,
             "local_decision_predictions":0,"independent_decision_gold":False},
    }
    return {
        "schema":"local-system-one/phase8_3-real-decision-feasibility-v1",
        "source":"three_published_historic_real_hermes_stepfun_case_summaries_only",
        "historical_case_ids":list(observations),
        "cohorts":observations,
        "historical_native_task_successes_with_published_verification":3,
        "recorded_real_local_decision_observations":2,
        "historical_raw_native_evidence_rechecked_in_this_audit":False,
        "separately_adjudicated_real_decision_gold_count":0,
        "qualified_rules_vs_laya_real_pairs":0,
        "real_decision_correctness_benchmark":"NOT_ESTABLISHED",
        "real_agent_level_cost_savings":"NOT_MEASURED",
        "provider_attempts_historical":8,
        "provider_HTTP_200_terminal_historical":7,
        "provider_outcome_unknown_historical":1,
        "provider_subscription_credit_spend":"UNKNOWN",
        "new_provider_calls_for_this_audit":0,
        "new_model_inferences_for_this_audit":0,
        "excluded_synthetic_stock_shadow_from_real_denominator":True,
        "active_authority":"NOT_AUTHORIZED",
        "interpretation":"Three authentic task successes do not supply independent decision gold; no causal real value accuracy estimate is supported.",
    }


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report",type=Path)
    args=ap.parse_args()
    try:
        outcome=assess_historical_data(historical_inputs())
    except (RealIntakeBlocked,ValueError,TypeError,KeyError,OSError) as exc:
        print(json.dumps({"status":"BLOCKED", "reason":type(exc).__name__},sort_keys=True))
        return 3
    if args.report:
        out=args.report.absolute()
        expected=ROOT/"results/processed/phase8_3_real_evidence_feasibility.json"
        if out!=expected or out.exists() or out.is_symlink():
            print(json.dumps({"status":"BLOCKED", "reason":"unsafe_report_path"}))
            return 3
        out.write_text(json.dumps(outcome,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(json.dumps(outcome,sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
