#!/usr/bin/env python3
"""Independent read-only verification of actual Hermes H3 Runtime-down trial.

Consumes private frozen original Agent/HTTP/HMAC/Provider evidence, and may
write ONE public allowlisted aggregate. No Hermes Agent execution, no
Laya runtime launch, no StepFun request, and no production state changes.

Original real H3 SOURCE is pinned to preregistration commit 40a7b44.
The verifier is post-run source, not represented as the tested executor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from local_system_one.budget_observability import reconcile_budget
from phase8_3_real_hermes_h3 import (
    PRIVATE, TEST_HOME, RUN_ID, _native_oracle,
    _correlate_h3, _read_jsonl,
)
from phase8_3_transport_closeout import (
    audited_snapshot, H1_ORIGINAL_SHA256, H2_ORIGINAL_SHA256,
)
from phase8_3_prepare_shared_dependency_home import (
    isolated_test_config,
)

FROZEN_H3="40a7b4416db07e6eedcf505131e0c9b3e1a98eac"
H3_LEDGER_SHA="5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb"
LEDGER_SNAPSHOT=PRIVATE/"provider_h1_h2_h3_frozen.private.jsonl"
ADAPTER_SNAPSHOT=PRIVATE/"h3_adapter_frozen.private.jsonl"
OUTPUT=ROOT/"results/processed/phase8_3_h3_real_stepfun_runtime_down.json"


class H3EvidenceError(ValueError):
    pass


def _private_obj(file: Path) -> dict:
    if file.is_symlink() or not file.is_file():
        raise H3EvidenceError("native private evidence absent or symlinked")
    obj=json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise H3EvidenceError("unexpected private evidence shape")
    return obj


def _private_rows(file: Path) -> list[dict]:
    if file.is_symlink() or not file.is_file():
        raise H3EvidenceError("private JSONL unavailable")
    rows=[json.loads(t) for t in file.read_text(encoding="utf-8").splitlines() if t.strip()]
    if not rows or not all(isinstance(r,dict) for r in rows):
        raise H3EvidenceError("non-object private rows")
    return rows


def h3_adapter_from_current_home(http: list[dict]) -> list[dict]:
    """Find exact H3 keyed requests among append-only H2/H3 plugin events.

    NOT a time-based filter. Later Hermes runs may append unrelated rows,
    but H3 entries must match BOTH the immutable H3 observer's request
    HMACs and native Session/Tool IDs (in _correlate_h3).
    """
    refs=[r.get("decision_request_ref") for r in http]
    if (len(refs)!=2 or len(set(refs))!=2
        or any(not isinstance(r,str) or len(r)!=32 for r in refs)):
        raise H3EvidenceError("H3 observer lacks two unique HMAC request refs")
    plugin=TEST_HOME/"plugin-data"
    if plugin.is_symlink() or not plugin.is_dir():
        raise H3EvidenceError("test-only Hermes plugin state unavailable")
    matched=[]
    for file in plugin.glob("*/state.json"):
        state=_private_obj(file)
        for name in ("completion_loop_probe_history","completion_shadow_history"):
            history=state.get(name,[])
            if not isinstance(history,list):
                raise H3EvidenceError("malformed H3 plugin history")
            for row in history:
                if isinstance(row,dict) and row.get("decision_request_ref") in refs:
                    if row.get("gate")!="completion" or row.get("mode")!="shadow":
                        raise H3EvidenceError("H3 keyed reference to wrong policy/mode")
                    matched.append({
                        key:row[key] for key in (
                            "gate","native_stage","session_ref","turn_ref",
                            "tool_call_ref","decision_request_ref",
                            "action_status","evidence_status",
                            "response_request_id_matches",
                        ) if key in row
                    })
    if len(matched)!=2 or {x.get("decision_request_ref") for x in matched}!=set(refs):
        raise H3EvidenceError("H3 native Adapter records missing/duplicate")
    if sorted(x.get("native_stage") for x in matched)!=["tool_result","turn_end"]:
        raise H3EvidenceError("H3 exact tool/end stages missing")
    if not all(x.get("action_status")=="failed_open" for x in matched):
        raise H3EvidenceError("H3 did not fail-open")
    return matched


def analyze(native: dict, prior: dict, physical: list[dict],
            group: dict, oracle: dict,
            adapter: list[dict], joined: dict, http: list[dict],
            *, digest: str) -> dict:
    if (
        native.get("code_sha")!=FROZEN_H3
        or native.get("run_id")!=RUN_ID
        or native.get("platform")!="hermes"
        or native.get("mode")!="shadow"
        or native.get("scenario")!="read_nonce"
        or native.get("main_model")!="stepfun/step-5-preview"
        or native.get("process_exit_code")!=0
        or native.get("timed_out") is not False
        or native.get("input_unchanged") is not True
        or native.get("read_proof",{}).get("final_answer_matches_nonce") is not True
        or native.get("provider_calls_counted_at_proxy")!=2
        or native.get("provider_global_used")!=8
    ):
        raise H3EvidenceError("original native H3 execution or tool outcome mismatch")
    if (
        prior.get("source_sha")!=FROZEN_H3
        or prior.get("run_id")!=RUN_ID
        or prior.get("h3_scoped_verdict")!="PASS_SCOPED"
        or prior.get("phase8_3a_overall")!="BLOCKED_HISTORICAL_H1_REQUEST"
        or prior.get("profile_off_restored") is not True
        or prior.get("background_title_llm_upgrade")!="DISABLED_TEST_HOME_ONLY"
    ):
        raise H3EvidenceError("original H3 runner provenance/policy is not supported")
    if not oracle.get("valid") or not all(oracle.get(k) is True for k in (
        "native_tool_call_result_id_paired",
        "original_file_bytes_match_tool",
        "final_answer_matches_original",
        "nonce_absent_from_prompt",
        "native_provider_route_confirmed",
    )):
        raise H3EvidenceError("native tool result is not independently verified")
    if (
        len(adapter)!=2
        or sorted(e.get("native_stage") for e in adapter)!=["tool_result","turn_end"]
        or any(e.get("action_status")!="failed_open" for e in adapter)
    ):
        raise H3EvidenceError("native Adapter fail-open events absent")
    if (
        joined.get("status")!="PASS"
        or joined.get("native_http_pairs_verified")!=2
        or joined.get("adapter_completion_observations")!=2
        or joined.get("issues")!=[]
    ):
        raise H3EvidenceError("exact H3 native-to-HTTP correlation not proven")
    if (
        len(http)!=2
        or any(e.get("http_status")!=503 or e.get("backend") is not None
               or e.get("decision_source") is not None
               or e.get("path")!="/v1/workflows/completion-gate"
               or e.get("response_matches_request_id") is not None
               for e in http)
    ):
        raise H3EvidenceError("H3 HTTP503/no-MLX failure observation contradicted")
    if (
        group.get("reserved_global")!=8
        or group.get("reserved_h1")!=3
        or group.get("reserved_h2")!=3
        or group.get("reserved_new")!=2
        or group.get("attempted_new")!=2
        or group.get("responded_new")!=2
        or group.get("unknown_new")!=0
        or group.get("finalized_new")!=2
        or group.get("historic_h1_unresolved")!=1
        or group.get("new_run_status")!="SCOPE_COMPLETE"
        or group.get("overall_phase_8_3a_integrity")!="BLOCKED_HISTORICAL_UNRESOLVED"
    ):
        raise H3EvidenceError("shared immutable H1/H2/H3 ledger is inconsistent")
    statuses=[r.get("http_status") for r in physical if (
        r.get("run")==RUN_ID and r.get("kind")=="responded")]
    if statuses!=[200,200]:
        raise H3EvidenceError("two true StepFun HTTP 200 results missing")
    original_digest=prior.get("provider_physical_ledger",{}).get("ledger_digest_sha256")
    if original_digest!=digest or digest!=H3_LEDGER_SHA:
        raise H3EvidenceError("H3 frozen private global Provider digest mismatch")
    usage=native.get("usage",{})
    if (
        usage.get("api_calls")!=2 or usage.get("completed") is not True
        or usage.get("failed") is not False
    ):
        raise H3EvidenceError("native Agent H3 main usage not observed")
    measured=reconcile_budget(
        physical,run_id=RUN_ID,total_cap=24,per_run_cap=3,
        agent_reported_calls=2,
        decision_calls={"gate_requests":2,"rule_decisions":0,
                        "model_inferences":0,"failed_or_timed_out":2},
        controlled_egress_verified=True,
    )
    historical=reconcile_budget(
        physical,run_id="h1_read_off",total_cap=24,per_run_cap=3,
        agent_reported_calls=2,controlled_egress_verified=True,
    )
    if (
        measured["budget_integrity"]!="PARTIAL"
        or measured["attempted_unresolved"]!=0
        or measured["provider_responded"]!=2
        or measured["proxy_attempts"]!=2
        or measured["unattributed_requests"]!=0
        or measured["unknown_cost_requests"]!=2
        or historical["budget_integrity"]!="BLOCKED"
        or historical["attempted_unresolved"]!=1
    ):
        raise H3EvidenceError("H3 accounting overstated or unresolved historical H1")
    return {
        "schema":"local-system-one/phase8_3-h3-real-native-adjudicated-v1",
        "original_real_execution_source_sha":FROZEN_H3,
        "platform":"hermes","native_mode":"shadow",
        "main_model":"stepfun/step-5-preview",
        "native_task":{
            "one_native_read_file_and_result_identity":True,
            "tool_bytes_match_original_file":True,
            "final_answer_matches_original_file":True,
            "file_was_not_mutated":True,
            "agent_exit_code":0,
            "observed_agent_elapsed_seconds":native.get("elapsed_seconds"),
            "outcome":"PASS_SCOPED",
        },
        "shadow_runtime_down":{
            "runtime_service":"INTENTIONALLY_NOT_RUNNING",
            "observed_completion_HTTP_503":2,
            "adapter_failed_open_observations":2,
            "native_adapter_http_exact_pairs":2,
            "observer_backends":[None,None],
            "causal_request_correlation":"PASS_SCOPED",
            "active_action_allowed":False,
        },
        "provider_physical":{
            "total_requests_reserved_so_far":8,
            "previous_h1_requests":3,
            "previous_h2_requests":3,
            "H3_attempted":2,
            "H3_responded_HTTP_200":2,
            "H3_unresolved":0,
            "H3_physically_unattributed":0,
            "original_h1_unresolved":1,
            "original_H1_prefix_sha256":H1_ORIGINAL_SHA256,
            "original_H1_H2_prefix_sha256":H2_ORIGINAL_SHA256,
            "H3_original_ledger_sha256":H3_LEDGER_SHA,
            "billing_provenance":"UNKNOWN",
            "H3_usage_accounting":"PARTIAL_TOKEN_BILLING",
        },
        "Hermes_self_reported_main_api_calls":2,
        "Hermes_self_reported_input_tokens":usage.get("input_tokens"),
        "Hermes_self_reported_output_tokens":usage.get("output_tokens"),
        "title_generation_test_home":{
            "background_model_upgrade":"DISABLED",
            "derived_nonmodel_title":"RETAINED",
            "H3_physical_vs_main_counts":"2_vs_2",
            "hypothesis_status":"SUPPORTS_BACKGROUND_TITLE_EXPLANATION_NOT_CAUSALLY_PROVEN",
            "historical_H1_H2_extra_request_identity":"UNKNOWN",
        },
        "test_profile_restored_off":True,
        "h3_scoped_qualification":"PASS_SCOPED",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_UNRESOLVED",
        "real_agent_cost_saving":"NOT_MEASURED",
        "actual_StepFun_plan_credit_debit":"UNKNOWN",
        "active_authority":"NOT_AUTHORIZED",
        "remaining_physical_slots_not_execution_authority":16,
        "other_native_tasks_not_run":["H4","DSH_D1_D2_D3_D4"],
    }


def _load_private() -> dict:
    physical=_private_rows(LEDGER_SNAPSHOT)
    digest=hashlib.sha256(LEDGER_SNAPSHOT.read_bytes()).hexdigest()
    if digest!=H3_LEDGER_SHA:
        raise H3EvidenceError("original H3 Provider ledger snapshot damaged")
    run=_private_obj(PRIVATE/"runs/h3_runtime_down/verified_summary.private.json")
    prior=_private_obj(PRIVATE/"runs/h3_verified.private.json")
    observer=_private_rows(PRIVATE/"h3_http.private.jsonl")
    key_file=PRIVATE/"h3_correlation_key.private.bin"
    if key_file.is_symlink() or not key_file.is_file() or key_file.stat().st_mode & 0o077:
        raise H3EvidenceError("H3 HMAC private key path/permission invalid")
    # Read ephemeral HMAC bytes only for in-memory correlation; never export
    # the bytes or assign them to a public-report field.
    hmac_key_bytes=key_file.read_bytes()
    if len(hmac_key_bytes)!=32:
        raise H3EvidenceError("H3 correlation key malformed")
    if ADAPTER_SNAPSHOT.is_file():
        adapter=_private_rows(ADAPTER_SNAPSHOT)
    else:
        adapter=h3_adapter_from_current_home(observer)
    result=_correlate_h3(hmac_key_bytes,adapter,observer)
    oracle=_native_oracle()
    report=analyze(run,prior,physical,
                   audited_snapshot(LEDGER_SNAPSHOT,new_run=RUN_ID),
                   oracle,adapter,result,observer,digest=digest)
    return {"report":report,"adapter":adapter}


def main() -> None:
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write-public-aggregate",action="store_true")
    cli.add_argument("--archive-adapter-private",action="store_true")
    args=cli.parse_args()
    try:
        read=_load_private()
        report=read["report"]
        if args.archive_adapter_private:
            if ADAPTER_SNAPSHOT.exists() or ADAPTER_SNAPSHOT.is_symlink():
                raise H3EvidenceError("refuse to overwrite original H3 adapter HMAC snapshot")
            payload="".join(json.dumps(row,sort_keys=True)+"\n" for row in read["adapter"])
            with ADAPTER_SNAPSHOT.open("x",encoding="utf-8") as out:
                out.write(payload)
                out.flush()
            ADAPTER_SNAPSHOT.chmod(0o600)
        if args.write_public_aggregate:
            if OUTPUT.exists() or OUTPUT.is_symlink():
                raise H3EvidenceError("refuse to overwrite original H3 public aggregation")
            OUTPUT.parent.mkdir(parents=True,exist_ok=True)
            OUTPUT.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",
                              encoding="utf-8")
        print(json.dumps(report,sort_keys=True,indent=2))
    except (OSError,ValueError,TypeError,KeyError,H3EvidenceError):
        print(json.dumps({
            "status":"BLOCKED",
            "new_main_provider_requests":0,
            "no_native_Agent_task_executed":True,
        }))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
