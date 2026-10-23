#!/usr/bin/env python3
"""Independently adjudicate genuine H4C failure *before any native Session*.

True H4C real-run source 8776de7 had a child exit 1 and original
Hermes one-shot usage failure SystemExit(1), but no exported traceback
because the official library suppresses stdout/stderr during _run_agent.
No original H4C Provider physical attempt, native tool, or Retry
observation occurred. The isolated test Home was rolled back OFF.

This verifier is READ-ONLY and cannot run Hermes, touch a credential,
send StepFun requests, restart a gateway, or modify original H4B.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from phase8_3_real_hermes_h2 import PRIVATE,ROOT,TEST_HOME
from phase8_3_transport_closeout import (
    audited_snapshot,H4C,H3_ORIGINAL_SHA256,
)

RUN_ID="h4c_missing_read"
ORIGINAL_SHA="8776de71a88821dffd84bfd4976927fd0cfe9c3a"
RECOVERY=PRIVATE/"h4c_recovery"
CASE=PRIVATE/"runs"/RUN_ID
OUT=ROOT/"results/processed/phase8_3_h4c_preactive_native_blocked.json"


class H4CIncidentBlocked(ValueError):
    pass


def _document(path:Path)->dict:
    if path.is_symlink() or not path.is_file():
        raise H4CIncidentBlocked("original private H4C evidence missing or symlinked")
    x=json.loads(path.read_text())
    if not isinstance(x,dict):
        raise H4CIncidentBlocked("invalid original H4C evidence schema")
    return x


def analyze(original:dict,usage:dict,receipt:dict,pids:dict,
            budget:dict,*,original_sessions:int,baseline_same:bool,
            target_absent:bool,observer_absent:bool,other_H4B_untouched:bool)->dict:
    if (original.get("candidate_source_sha")!=ORIGINAL_SHA or
        original.get("run_id")!=RUN_ID or
        original.get("agent_platform")!="official_hermes_inprocess_AIAgent" or
        original.get("native_child_exit_code")!=1 or
        original.get("native_child_timed_out") is not False or
        original.get("private_original_file_still_missing") is not True or
        original.get("h4c_acceptance")!="NOT_YET_ADJUDICATED"):
        raise H4CIncidentBlocked("original frozen H4C result disagrees")
    if (usage.get("failure")!="SystemExit(1)" or
        usage.get("failed") is not True or
        usage.get("api_calls") not in (0,None)):
        raise H4CIncidentBlocked("the genuine Hermes failure class was altered")
    if (receipt.get("status")!="TEST_HOME_STATE_RESTORED" or
        receipt.get("mode")!="off" or
        receipt.get("credential_metadata_unchanged") is not True or
        receipt.get("sqlite_logical_snapshot_restored") is not True or
        receipt.get("plugin_private_state_restored") is not True or
        receipt.get("public_plugin_source_restored") is not True or
        receipt.get("test_config_restored") is not True or
        receipt.get("production_files_touched") is not False):
        raise H4CIncidentBlocked("H4C rollback is not proven")
    if (pids.get("recorded_child_groups")!=4 or
        pids.get("all_stopped") is not True or
        pids.get("production_processes_discovered_or_touched") is not False or
        any(x!="NOT_RUNNING" for x in pids.get("statuses",{}).values())):
        raise H4CIncidentBlocked("original H4C process groups did not cleanly stop")
    if (budget.get("reserved_global")!=8 or
        budget.get("reserved_h1")!=3 or
        budget.get("reserved_h2")!=3 or
        budget.get("reserved_h3")!=2 or
        budget.get("reserved_original_h4")!=0 or
        budget.get("reserved_original_h4b")!=0 or
        budget.get("reserved_new")!=0 or
        budget.get("attempted_new")!=0 or
        budget.get("historic_h1_unresolved")!=1 or
        budget.get("ledger_digest_sha256")!=H3_ORIGINAL_SHA256):
        raise H4CIncidentBlocked("original Provider physical request accounting drifted")
    if not all((original_sessions==0,baseline_same,target_absent,
                observer_absent,other_H4B_untouched)):
        raise H4CIncidentBlocked("H4C no-native / rollback / old-history evidence contradicted")
    return {
        "schema":"local-system-one/phase8_3-h4c-native-init-blocked-v1",
        "frozen_original_source_sha":ORIGINAL_SHA,
        "case":RUN_ID,
        "original_H4_and_H4B_evidence_unchanged":True,
        "official_Hermes_one_shot_child_exit":1,
        "genuine_Hermes_original_failure_class":"SystemExit(1)",
        "underlying_initialization_cause":"NOT_DETERMINABLE_FROM_ORIGINAL_SUPPRESSED_STDERR",
        "actual_native_session_or_read_file_tool_call":False,
        "actual_Completion_And_Retry_observations":False,
        "new_StepFun_physical_requests":0,
        "global_StepFun_request_count":8,
        "original_H1_unknown_outcome":1,
        "disposable_H4C_target_still_absent":True,
        "local_snapshot_sqlite_restored":True,
        "local_test_Hermes_plugin_config_restored":True,
        "test_auth_metadata_unchanged":True,
        "test_profile_restored_off":True,
        "H4C_owned_process_groups_stopped":4,
        "production_gateway_modified":False,
        "git_main_or_NAS_main_modified":False,
        "H4C_outcome":"BLOCKED_BEFORE_NATIVE_SESSION_AND_PROVIDER",
        "H4C_real_file_failure_qualification":"NOT_RUN",
        "real_Retry_gate_qualification":"NOT_RUN",
        "automatic_H4C_rerun_authorized":False,
        "next_safe_step":"ZERO_NETWORK_REAL_AGENT_INITIALIZATION_STAGE_DIAGNOSTIC",
        "active_authority":"NOT_AUTHORIZED",
    }


def verify()->dict:
    original=_document(PRIVATE/"runs/h4c_verified.private.json")
    usage=_document(CASE/"usage.private.json")
    receipt=_document(RECOVERY/"rollback_status.private.json")
    manifest=_document(RECOVERY/"manifest.private.json")
    pidfile=RECOVERY/"owned_process_groups.private.jsonl"
    if pidfile.is_symlink() or not pidfile.is_file():
        raise H4CIncidentBlocked("H4C private process provenance ledger missing")
    from phase8_3_h4b_owned_processes import bind_case,inspect_owned
    import phase8_3_h4b_owned_processes as owned
    previous=owned.CASE_ID
    try:
        bind_case(RUN_ID)
        pids=inspect_owned()
    finally:
        bind_case(previous)
    budget=audited_snapshot(PRIVATE/"provider_real_ledger.private.jsonl",
                            new_run=H4C)
    path=RECOVERY/"state_after.private.db"
    if path.is_symlink() or not path.is_file():
        raise H4CIncidentBlocked("postrun H4C private SQLite snapshot not found")
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro",
                         uri=True,timeout=4) as db:
        sessions=db.execute("SELECT COUNT(*) FROM sessions WHERE cwd=?",
                            (str(CASE.resolve()),)).fetchone()[0]
    pre=RECOVERY/"state_before.private.db"
    if pre.is_symlink() or not pre.is_file():
        raise H4CIncidentBlocked("H4C original SQLite checkpoint missing")
    from phase8_3_h4b_transaction import bind_case as bind_rollback,inspect as check_rollback
    import phase8_3_h4b_transaction as transaction
    old=transaction.CASE_ID
    try:
        bind_rollback(RUN_ID)
        status=check_rollback()
    finally:
        bind_rollback(old)
    baseline=(
        status["auth_metadata_unchanged"] is True and
        status["original_sqlite_digest_matches_before"] is True and
        status["current_profile_state_matches_before"] is True and
        manifest.get("case_id")==RUN_ID and
        manifest.get("credentials_copied") is False
    )
    target_manifest=_document(CASE/"h4c_missing_target.private.json")
    target=Path(target_manifest.get("path",""))
    if target.parent!=CASE or not target.name.startswith("h4c_absent_"):
        raise H4CIncidentBlocked("H4C original target manifest inconsistent")
    from phase8_3_verify_h4b_seatbelt_block import verify as h4b_old
    # The prior H4B verifier imports fixed old H4B constants; invoke only
    # after ensuring the global tx/PID scopes were restored.
    earlier=h4b_old()
    other_H4B=bool(
        earlier["H4B_scoped_verdict"]=="BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION" and
        earlier["original_test_sqlite_logically_restored"] is True and
        earlier["model_provider_physical_attempts"]==0
    )
    return analyze(
        original,usage,receipt,pids,budget,
        original_sessions=sessions,
        baseline_same=baseline,
        target_absent=not target.exists() and not target.is_symlink(),
        observer_absent=not (PRIVATE/"h4c_http.private.jsonl").exists(),
        other_H4B_untouched=other_H4B,
    )


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write-public",action="store_true")
    a=p.parse_args()
    try:
        result=verify()
        if a.write_public:
            if OUT.exists() or OUT.is_symlink():
                raise H4CIncidentBlocked("public H4C original incident cannot be overwritten")
            OUT.parent.mkdir(parents=True,exist_ok=True)
            OUT.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        print(json.dumps(result,sort_keys=True,indent=2))
    except (H4CIncidentBlocked,ValueError,OSError,TypeError,KeyError,sqlite3.Error):
        print(json.dumps({"status":"BLOCKED","new_provider_calls":0}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
