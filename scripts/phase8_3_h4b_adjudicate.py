#!/usr/bin/env python3
"""Independent, credential-free H4B real-native failure/Retry HMAC adjudication.

The ORCHESTRATOR only says whether an isolated native process exited and
its test-Home was rolled back. H4B is accepted ONLY after a separate
read-only verifier checks the archived post-run Hermes SQLite, exact
original private missing-file manifest, original pre/post plugin state,
actual localhost HTTP observer records, keyed native tool/turn/Retry
provenance, original cumulative Provider ledger and the recovery receipt.

No native AIAgent, Provider call or plugin mutation in this verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from phase8_3_real_hermes_h4b import (
    PRIVATE, ROOT, RUN_ID, CASE_DIR, PROVIDER_LEDGER,
)
from phase8_3_h4b_transaction import (
    PRE_STATE, POST_STATE, POST_DB, FINAL_REPORT,
)
from phase8_3_h4_failure_oracle import (
    check_sqlite_failed_read, NativeH4OracleBlocked,
)
from phase8_3_h4_retry_evidence import (
    verify_retry_exact, RetryEvidenceBlocked,
)
from phase8_3_transport_closeout import (
    audited_snapshot, CloseoutBlocked, H3_ORIGINAL_SHA256,
)

PUBLIC=ROOT/"results/processed/phase8_3_h4b_real_native_adjudicated.json"
HMAC_FILE=PRIVATE/"h4b_correlation_key.private.bin"
OBSERVER=PRIVATE/"h4b_http.private.jsonl"


class AdjudicationBlocked(ValueError):
    pass


def configure_for_case(case_id: str) -> None:
    """One H4C independent verifier process; NEVER read H4B postrun by default."""
    global RUN_ID, CASE_DIR, POST_DB, PRE_STATE, POST_STATE
    global FINAL_REPORT, HMAC_FILE, OBSERVER, PUBLIC, PROVIDER_LEDGER, PRIVATE
    if case_id not in {"h4c_missing_read","h4d_missing_read","h4e_missing_read"}:
        raise AdjudicationBlocked("only the new H4C private evidence scope is accepted")
    import phase8_3_h4b_transaction as tx
    tx.bind_case(case_id)
    RUN_ID=case_id
    PRIVATE=tx.PRIVATE
    CASE_DIR=PRIVATE/"runs"/case_id
    POST_DB=tx.POST_DB
    PRE_STATE=tx.PRE_STATE
    POST_STATE=tx.POST_STATE
    FINAL_REPORT=tx.FINAL_REPORT
    short=case_id.split("_")[0]
    HMAC_FILE=PRIVATE/f"{short}_correlation_key.private.bin"
    OBSERVER=PRIVATE/f"{short}_http.private.jsonl"
    PUBLIC=ROOT/f"results/processed/phase8_3_{short}_real_native_adjudicated.json"
    if short=="h4e":
        HMAC_FILE=PRIVATE/"observer/correlation_key.private.bin"
        OBSERVER=PRIVATE/"observer/http.private.jsonl"
        PUBLIC=PRIVATE/"adjudication.private.json"
    if short in {"h4d","h4e"}:
        PROVIDER_LEDGER=(Path.home()/"Projects/system-one-phase8-3/private/phase8_3_native_real"
                         /"provider_real_ledger.private.jsonl")


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise AdjudicationBlocked("H4B original private document missing")
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict):
        raise AdjudicationBlocked("H4B private evidence shape invalid")
    return value


def _read_rows(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        return []
    rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
          if line.strip()]
    if not all(isinstance(row,dict) for row in rows):
        raise AdjudicationBlocked("H4B HTTP observer rows malformed")
    return rows


def _adapter_history_delta() -> dict[str,list[dict]]:
    before=_read_json(PRE_STATE)
    after=_read_json(POST_STATE)
    out={}
    for key in (
        "completion_loop_probe_history",
        "completion_shadow_history",
        "retry_escalation_shadow_history",
    ):
        a=before.get(key,[])
        b=after.get(key,[])
        if (not isinstance(a,list) or not isinstance(b,list)
                or len(b)<len(a) or b[:len(a)]!=a):
            raise AdjudicationBlocked("original H4B Adapter state not append-only")
        if len(b)-len(a)>3:
            raise AdjudicationBlocked("extra concurrent H4B Adapter events")
        out[key]=b[len(a):]
    return out


def _adapter_allowlisted(events: list[dict], gate: str) -> list[dict]:
    select=(
        "gate","mode","native_stage","session_ref","turn_ref",
        "tool_call_ref","decision_request_ref","request_id",
        "response_request_id_matches","action_status","action_reason",
        "decision","evidence_status",
    )
    rows=[]
    for record in events:
        if not isinstance(record,dict) or record.get("gate")!=gate:
            raise AdjudicationBlocked("untrusted adapter event gate or shape")
        rows.append({k:record[k] for k in select if k in record})
    return rows


def _completion_join(completion: list[dict], http: list[dict],key: bytes) -> dict:
    from phase8_2b_native_correlate import correlate
    try:
        joined=correlate("hermes",POST_DB,completion,http,key)
    except (ValueError,TypeError,sqlite3.Error,OSError):
        return {"status":"BLOCKED","native_http_pairs_verified":0}
    return {
        "status":joined.get("status"),
        "native_http_pairs_verified":joined.get("native_http_pairs_verified"),
        "adapter_completion_observations":joined.get("adapter_completion_observations"),
        "issues":joined.get("issues"),
    }


def adjudicate(*, frozen_sha: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}",frozen_sha):
        raise AdjudicationBlocked("explicit frozen real H4B candidate source required")
    original=_read_json(PRIVATE/"runs"/f"{RUN_ID.split('_')[0]}_verified.private.json")
    if (original.get("candidate_source_sha")!=frozen_sha
            or original.get("run_id")!=RUN_ID
            or original.get("agent_platform")!="official_hermes_inprocess_AIAgent"):
        raise AdjudicationBlocked("H4B independent source identity mismatch")
    receipt=_read_json(FINAL_REPORT)
    if (receipt.get("status")!="TEST_HOME_STATE_RESTORED"
            or receipt.get("mode")!="off"
            or receipt.get("credential_metadata_unchanged") is not True
            or receipt.get("sqlite_logical_snapshot_restored") is not True
            or receipt.get("plugin_private_state_restored") is not True
            or receipt.get("test_config_restored") is not True
            or receipt.get("public_plugin_source_restored") is not True):
        raise AdjudicationBlocked("reversible H4B test Home restoration not proven")
    history=audited_snapshot(PROVIDER_LEDGER,new_run=RUN_ID)
    if (history.get("reserved_h1")!=3
            or history.get("reserved_h2")!=3
            or history.get("reserved_h3")!=2
            or history.get("reserved_original_h4")!=0
            or (RUN_ID in {"h4c_missing_read","h4d_missing_read","h4e_missing_read"}
                and history.get("reserved_original_h4b")!=0)
            or history.get("historic_h1_unresolved")!=1
            or not 8<=history.get("reserved_global",0)<=11
            or not 0<=history.get("attempted_new",0)<=3
            or history["reserved_global"]!=8+history["reserved_new"]):
        raise AdjudicationBlocked("physical history or H4B allowed slots altered")
    if not POST_DB.is_file() or POST_DB.is_symlink():
        raise AdjudicationBlocked("immutable post-run native SQLite archive unavailable")
    try:
        native=check_sqlite_failed_read(
            POST_DB,CASE_DIR,expected_case=RUN_ID)
        negative_pass=bool(
            native.get("tool_calls_exactly_one") is True
            and native.get("native_result_structured_missing_file") is True
            and native.get("tool_call_result_identity_paired") is True
            and native.get("target_absent_before_and_after") is True
        )
    except (NativeH4OracleBlocked,ValueError,OSError,sqlite3.Error):
        native={
            "native_result_structured_missing_file":False,
            "tool_calls_exactly_one":False,
            "native_failure_status_propagated_to_retry_hook":"NOT_ESTABLISHED",
        }
        negative_pass=False
    delta=_adapter_history_delta()
    completion=_adapter_allowlisted(
        delta["completion_loop_probe_history"]+
        delta["completion_shadow_history"],"completion")
    retry=_adapter_allowlisted(
        delta["retry_escalation_shadow_history"],"retry_escalation")
    http=_read_rows(OBSERVER)
    c_http=[row for row in http
            if row.get("path")=="/v1/workflows/completion-gate"]
    retry_http=[row for row in http
                if row.get("path")=="/v1/workflows/retry-escalation-gate"]
    key=b""
    if HMAC_FILE.is_file() and not HMAC_FILE.is_symlink() and (
            HMAC_FILE.stat().st_mode&0o077)==0:
        key=HMAC_FILE.read_bytes()
    if len(key)!=32:
        raise AdjudicationBlocked("post-run H4B HMAC key unavailable/unsafe")
    join=_completion_join(completion,c_http,key) if completion else {
        "status":"NOT_ESTABLISHED","native_http_pairs_verified":0}
    try:
        retry_match=verify_retry_exact(
            POST_DB,CASE_DIR,key,
            retry_adapter=retry,
            completion_adapter=completion,http=http,
            expected_case=RUN_ID,
        )
    except (RetryEvidenceBlocked,ValueError,OSError,sqlite3.Error):
        retry_match={
            "native_retry_tool_hmac_match":False,
            "retry_http_hmac_exact_match":False,
            "status":"NOT_VERIFIED",
        }
    physical_pass=bool(
        history.get("new_run_status")=="SCOPE_COMPLETE"
        and 1<=history.get("reserved_new",0)<=3
        and history.get("unknown_new")==0
        and history.get("reserved_new")==history.get("attempted_new")
        ==history.get("responded_new")==history.get("finalized_new")
    )
    completion_pass=bool(
        len(c_http)==2 and len(completion)==2
        and len(retry_http)==1 and len(http)==3
        and all(row.get("http_status")==200 and row.get("backend")=="mlx"
                and row.get("response_matches_request_id") is True
                for row in c_http)
        and join.get("status")=="PASS"
        and join.get("native_http_pairs_verified")==2
    )
    retry_pass=bool(
        negative_pass
        and len(retry)==1
        and len(retry_http)==1
        and retry_match.get("native_retry_tool_hmac_match") is True
        and retry_match.get("retry_http_hmac_exact_match") is True
    )
    scoped=bool(
        original.get("native_child_exit_code")==0
        and original.get("native_child_timed_out") is False
        and original.get("error_class") is None
        and original.get("private_original_file_still_missing") is True
        and negative_pass and physical_pass and completion_pass and retry_pass
    )
    return {
        "schema":f"local-system-one/phase8_3-{RUN_ID.split('_')[0]}-native-readfailure-adjudicated-v1",
        "original_run_source_sha":frozen_sha,
        "is_original_H4_gateway_attempt":False,
        "native_engine":"installed_official_Hermes_AIAgent_inprocess",
        "sandbox":"macOS_Seatbelt_exact_file_write_and_localhost_ports",
        "model":"stepfun/step-5-preview",
        "mode":"shadow",
        "native_missing_file_tool_oracle":"PASS" if negative_pass else "NOT_VERIFIED",
        "native_exactly_one_read_file":native.get("tool_calls_exactly_one") is True,
        "native_structured_error":native.get("native_result_structured_missing_file") is True,
        "completion_actual_http_200":len(c_http),
        "completion_native_adapter_http_links":join.get("native_http_pairs_verified",0),
        "completion_verdict":"PASS" if completion_pass else "NOT_VERIFIED",
        "retry_actual_http_events":len(retry_http),
        "retry_native_tool_hmac_proven":retry_match.get("native_retry_tool_hmac_match") is True,
        "retry_decision_advisory_only":retry_match.get(
            "no_native_retry_or_active_action_observed_from_advisor") is True,
        "retry_verdict":"PASS" if retry_pass else "NOT_VERIFIED",
        "global_provider_reservations":history["reserved_global"],
        "physical_attempts_for_current_case":history["attempted_new"],
        "H4B_physical_attempts":history["attempted_new"] if RUN_ID=="h4b_missing_read" else 0,
        "physical_provider_responded_for_current_case":history["responded_new"],
        "physical_provider_unknown_for_current_case":history["unknown_new"],
        "H4B_physical_responded":history["responded_new"] if RUN_ID=="h4b_missing_read" else 0,
        "H4B_physical_unknown":history["unknown_new"] if RUN_ID=="h4b_missing_read" else 0,
        "H1_original_unresolved":history["historic_h1_unresolved"],
        "provider_ledger_sha256":history["ledger_digest_sha256"],
        "physical_budget_verdict":"PASS" if physical_pass else "NOT_VERIFIED",
        "isolated_test_home_reverted_to_OFF":True,
        "original_SQLite_and_plugin_state_restored":True,
        "auth_metadata_unchanged":True,
        "read_or_backed_up_provider_key":False,
        "actual_subscription_credit_debit":"UNKNOWN",
        "agent_level_savings":"NOT_MEASURED",
        f"{RUN_ID.split('_')[0].upper()}_scoped_verdict":"PASS_SCOPED" if scoped else "PARTIAL_OR_BLOCKED",
        "phase8_3a_global":"BLOCKED_HISTORICAL_H1_UNRESOLVED",
        "original_H4_unchanged":True,
        "native_active_authority":"NOT_AUTHORIZED",
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frozen-sha",required=True)
    p.add_argument("--write-public",action="store_true")
    args=p.parse_args()
    try:
        result=adjudicate(frozen_sha=args.frozen_sha)
        if args.write_public:
            if PUBLIC.exists() or PUBLIC.is_symlink():
                raise AdjudicationBlocked("cannot overwrite original H4B public aggregate")
            PUBLIC.parent.mkdir(parents=True,exist_ok=True)
            PUBLIC.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                              encoding="utf-8")
        print(json.dumps(result,sort_keys=True,indent=2))
        if result[f"{RUN_ID.split('_')[0].upper()}_scoped_verdict"]!="PASS_SCOPED":
            raise SystemExit(3)
    except (AdjudicationBlocked,OSError,ValueError,TypeError,
            KeyError,sqlite3.Error,CloseoutBlocked):
        print(json.dumps({"status":"BLOCKED",
                          "new_Provider_requests":0,
                          "no_native_Agent_started_by_verifier":True}))
        raise SystemExit(3) from None

if __name__=="__main__":
    main()
