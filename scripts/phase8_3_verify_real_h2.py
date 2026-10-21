#!/usr/bin/env python3
"""Independent private H2 native + real Provider + local MLX verifier.

Only reads post-run private evidence and may write ONE new allowlisted
public aggregate. Never launches Hermes, a model runtime or any Provider
request. A H2 scoped PASS can coexist with historical H1 overall BLOCKED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from local_system_one.budget_observability import reconcile_budget
from phase8_3_real_hermes_h2 import (
    RUN_ID, PRIVATE, TEST_HOME, _native_oracle, _native_http_correlate, _read_jsonl,
)
from phase8_3_transport_closeout import audited_snapshot, H1_ORIGINAL_SHA256

FROZEN_H2 = "0dc626ff86038702f74027b4a988d21f096f72d9"
OUTPUT = ROOT / "results/processed/phase8_3_h2_real_stepfun_shadow.json"


class H2EvidenceError(ValueError):
    pass


def _one(path: Path) -> dict:
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise H2EvidenceError("invalid private source object")
    return obj


def _rows(path: Path) -> list[dict]:
    rows=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not all(isinstance(x,dict) for x in rows):
        raise H2EvidenceError("invalid Provider ledger")
    return rows


def analyze(native: dict, prior_run: dict, physical: list[dict],
            group: dict, original_oracle: dict,
            joined: dict, http: list[dict], *, digest: str) -> dict:
    """Pure, strict artifact-to-evidence transformer with predeclared labels."""
    if (
        native.get("run_id")!=RUN_ID or native.get("code_sha")!=FROZEN_H2
        or native.get("platform")!="hermes" or native.get("mode")!="shadow"
        or native.get("scenario")!="read_nonce" or native.get("main_model")!="stepfun/step-5-preview"
        or native.get("process_exit_code")!=0 or native.get("timed_out") is not False
        or native.get("input_unchanged") is not True
        or native.get("read_proof",{}).get("final_answer_matches_nonce") is not True
    ):
        raise H2EvidenceError("native H2 source/run/tool status contradicts frozen plan")
    if prior_run.get("source_sha")!=FROZEN_H2 or prior_run.get("run_id")!=RUN_ID:
        raise H2EvidenceError("original H2 runner summary does not match frozen source")
    if prior_run.get("h2_scoped_verdict")!="PASS_SCOPED":
        raise H2EvidenceError("H2 original runner did not pass its scoped checks")
    if prior_run.get("phase8_3a_overall")!="BLOCKED_HISTORICAL_H1_UNRESOLVED":
        raise H2EvidenceError("H1 budget history was incorrectly promoted")
    if not original_oracle.get("valid") or not all(
        original_oracle.get(k) is True for k in (
            "native_tool_call_result_identity","tool_bytes_match_original",
            "agent_answer_matches_original","input_absent_from_prompt",
            "native_provider_proxy_route")
    ):
        raise H2EvidenceError("original file/native result could not be verified")
    if (
        joined.get("status")!="PASS" or joined.get("native_http_pairs_verified")!=2
        or joined.get("adapter_completion_observations")!=2 or joined.get("issues")!=[]
    ):
        raise H2EvidenceError("native/Adapter/HTTP identity correlation is not exact")
    if (len(http)!=2 or any(e.get("http_status")!=200 or e.get("backend")!="mlx"
                            or e.get("decision_source")!="model"
                            or e.get("response_matches_request_id") is not True
                            or e.get("path")!="/v1/workflows/completion-gate"
                            for e in http)):
        raise H2EvidenceError("real local MLX/HTTP completion provenance missing")
    if (
        group.get("reserved_global")!=6 or group.get("reserved_h1")!=3
        or group.get("reserved_new")!=3 or group.get("attempted_new")!=3
        or group.get("responded_new")!=3 or group.get("finalized_new")!=3
        or group.get("unknown_new")!=0 or group.get("historic_h1_unresolved")!=1
        or group.get("new_run_status")!="SCOPE_COMPLETE"
        or group.get("overall_phase_8_3a_integrity")!="BLOCKED_HISTORICAL_UNRESOLVED"
    ):
        raise H2EvidenceError("shared global/H2 physical request budget evidence invalid")
    raw_status=[
        e.get("http_status") for e in physical
        if e.get("run")==RUN_ID and e.get("kind")=="responded"
    ]
    if raw_status!=[200,200,200]:
        raise H2EvidenceError("three independent real StepFun HTTP200 responses absent")
    if native.get("provider_calls_counted_at_proxy")!=3 or native.get("provider_global_used")!=6:
        raise H2EvidenceError("native runner's Provider count disagrees with physical ledger")
    if prior_run.get("provider_physical_ledger",{}).get("ledger_digest_sha256")!=digest:
        raise H2EvidenceError("original H2 post-run private physical ledger SHA mismatch")
    user_calls=native.get("usage",{}).get("api_calls")
    if (user_calls!=2 or native.get("usage",{}).get("completed") is not True
        or native.get("usage",{}).get("failed") is not False):
        raise H2EvidenceError("native self-reported model usage or outcome incomplete")
    budget_h2=reconcile_budget(
        physical,run_id=RUN_ID,per_run_cap=3,total_cap=24,
        agent_reported_calls=user_calls,
        decision_calls={"gate_requests":2,"rule_decisions":0,
                        "model_inferences":2,"failed_or_timed_out":0},
        controlled_egress_verified=True,
    )
    budget_h1=reconcile_budget(
        physical,run_id="h1_read_off",per_run_cap=3,total_cap=24,
        agent_reported_calls=2,decision_calls={
            "gate_requests":0,"rule_decisions":0,"model_inferences":0,
            "failed_or_timed_out":0},
        controlled_egress_verified=True,
    )
    if (
        budget_h2["budget_integrity"]!="PARTIAL"
        or budget_h2["attempted_unresolved"]!=0
        or budget_h2["provider_responded"]!=3
        or budget_h2["unattributed_requests"]!=1
        or budget_h2["unknown_cost_requests"]!=3
        or budget_h1["budget_integrity"]!="BLOCKED"
        or budget_h1["attempted_unresolved"]!=1
    ):
        raise H2EvidenceError("honest partial usage or historical H1 blocker missing")
    return {
        "schema":"local-system-one/phase8_3-real-h2-adjudicated-v1",
        "original_native_execution_sha":FROZEN_H2,
        "platform":"hermes","native_mode":"shadow",
        "main_model":"stepfun/step-5-preview",
        "local_model":"laya-typed-decisions-421m/mlx",
        "h2_native":{
            "tool_result_identity_verified":True,
            "tool_result_matches_independent_file":True,
            "agent_final_matches_independent_file":True,
            "native_exit_code":0,
            "task_outcome":"PASS_SCOPED",
            "observed_native_elapsed_seconds":native.get("elapsed_seconds"),
        },
        "h2_physical_provider":{
            "global_physical_attempts_total":group["reserved_global"],
            "original_h1_physical_attempts":group["reserved_h1"],
            "h2_physical_attempts":budget_h2["proxy_attempts"],
            "h2_provider_responses_HTTP_200":budget_h2["provider_responded"],
            "h2_attempted_unresolved":budget_h2["attempted_unresolved"],
            "h2_physically_unattributed":budget_h2["unattributed_requests"],
            "h2_provider_token_usage_source":"UNKNOWN",
            "h2_actual_subscription_credit_debit":"UNKNOWN",
            "h2_budget_integrity":"PARTIAL_USAGE_ATTRIBUTION",
            "immutable_original_h1_ledger_prefix_sha256":H1_ORIGINAL_SHA256,
            "historical_h1_unresolved":1,
            "historical_h1_budget_integrity":"BLOCKED",
            "h2_private_ledger_sha256":digest,
        },
        "h2_local_laya":{
            "completion_HTTP_200":2,
            "mlx_model_decision_observed":2,
            "strict_native_adapter_http_joined":joined["native_http_pairs_verified"],
            "exact_causal_correlation":"PASS_SCOPED",
            "runtime_models_used":["mlx"],
        },
        "hermes_self_reported_main_calls":user_calls,
        "hermes_self_reported_input_tokens":native["usage"].get("input_tokens"),
        "hermes_self_reported_output_tokens":native["usage"].get("output_tokens"),
        "real_agent_tokens_saved":"NOT_MEASURED",
        "real_agent_time_saved":"NOT_MEASURED",
        "active_authority":"NOT_AUTHORIZED",
        "h2_scoped_qualification":"PASS_SCOPED",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_REQUEST",
        "provider_total_request_authorization":"CAPPED_24_NOT_RENEWED",
        "all_other_native_tasks_in_this_round":"NOT_EXECUTED",
    }


def read_private_evidence() -> dict:
    root=PRIVATE
    ledger=root/"provider_real_ledger.private.jsonl"
    physical=_rows(ledger)
    digest=hashlib.sha256(ledger.read_bytes()).hexdigest()
    return analyze(
        _one(root/"runs"/RUN_ID/"verified_summary.private.json"),
        _one(root/"runs/h2_verified.private.json"),
        physical,audited_snapshot(ledger),
        _native_oracle(),
        _native_http_correlate(
            (root/"h2_correlation_key.private.bin").read_bytes(),
            _read_jsonl(root/"h2_http.private.jsonl")),
        _read_jsonl(root/"h2_http.private.jsonl"),
        digest=digest,
    )


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-public-aggregate",action="store_true")
    a=parser.parse_args()
    try:
        report=read_private_evidence()
        if a.write_public_aggregate:
            if OUTPUT.exists():
                raise H2EvidenceError("refuse to overwrite original independently reviewed H2 aggregate")
            OUTPUT.parent.mkdir(parents=True,exist_ok=True)
            OUTPUT.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps(report,sort_keys=True,indent=2))
    except (H2EvidenceError,OSError,ValueError,TypeError,KeyError):
        print(json.dumps({"status":"BLOCKED",
                          "new_main_provider_requests":0,
                          "agent_tasks_executed_by_verifier":0}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
