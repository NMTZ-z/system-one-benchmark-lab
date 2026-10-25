#!/usr/bin/env python3
"""Independent post-run H4B sandbox denial, rollback and zero-Provider adjudication.

The original one-shot H4B on FROZEN SHA 633c914 exited BEFORE
official Hermes _run_agent could construct an AIAgent: the Seatbelt
denied a harmless /dev/null stdout redirect. This was a genuine
macOS policy blocker, not a model/tool/Retry trial.

This script READS ONLY the original private stderr metadata, test
Home rollback receipt, postrun SQLite snapshot, original absent
target manifest, owned-process ledger and original shared physical
Provider ledger. It NEVER invokes an Agent, reads token contents,
issues a paid request or weakens the Seatbelt. Public output
contains only allowlisted safety status and immutable digests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

import yaml

from phase8_3_h4_failure_oracle import manifest_target
from phase8_3_h4b_transaction import (
    TEST_HOME, CONFIG, PRE_DB, POST_DB,
    PRE_STATE, POST_STATE, MANIFEST, FINAL_REPORT,
    _db_digest, inspect as inspect_recovery,
)
from phase8_3_h4b_owned_processes import inspect_owned
from phase8_3_real_hermes_h2 import ROOT,PRIVATE
from phase8_3_transport_closeout import (
    audited_snapshot,H4B,H3_ORIGINAL_SHA256,
)
from phase8_3_prepare_shared_dependency_home import isolated_test_config

SOURCE="633c914fe9b78b7515cfcfbe4795f5d2dbd3aadf"
OUTPUT=ROOT/"results/processed/phase8_3_h4b_seatbelt_admission_blocked.json"
RUN_ID=H4B


class SandboxIncidentBlocked(ValueError):
    pass


def _json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise SandboxIncidentBlocked("original private H4B evidence unavailable")
    x=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(x,dict):
        raise SandboxIncidentBlocked("original H4B evidence is not a JSON object")
    return x


def analyze(original: dict, rollback: dict, process: dict, ledger: dict,
            *, stderr: str, native_sessions: int,
            old_sqlite_digest: str, restored_sqlite_digest: str,
            target_absent: bool) -> dict:
    if (
        original.get("candidate_source_sha")!=SOURCE
        or original.get("run_id")!=RUN_ID
        or original.get("native_child_exit_code")!=1
        or original.get("native_child_timed_out") is not False
        or original.get("error_class") is not None
        or original.get("h4b_acceptance")!="NOT_YET_ADJUDICATED"
        or original.get("private_original_file_still_missing") is not True
    ):
        raise SandboxIncidentBlocked("frozen original H4B child execution mismatch")
    if (rollback.get("status")!="TEST_HOME_STATE_RESTORED"
            or rollback.get("mode")!="off"
            or rollback.get("credential_metadata_unchanged") is not True
            or rollback.get("sqlite_logical_snapshot_restored") is not True
            or rollback.get("plugin_private_state_restored") is not True
            or rollback.get("public_plugin_source_restored") is not True
            or rollback.get("test_config_restored") is not True
            or rollback.get("production_files_touched") is not False):
        raise SandboxIncidentBlocked("reversible test Home source/state evidence incomplete")
    if (process.get("all_stopped") is not True
            or process.get("recorded_child_groups")!=4
            or any(v!="NOT_RUNNING" for v in process.get("statuses",{}).values())
            or process.get("production_processes_discovered_or_touched") is not False):
        raise SandboxIncidentBlocked("not all owned H4B process groups were terminated")
    if (ledger.get("ledger_digest_sha256")!=H3_ORIGINAL_SHA256
            or ledger.get("reserved_global")!=8
            or ledger.get("reserved_new")!=0
            or ledger.get("attempted_new")!=0
            or ledger.get("reserved_original_h4")!=0
            or ledger.get("historic_h1_unresolved")!=1):
        raise SandboxIncidentBlocked("original shared Provider ledger was modified")
    if (native_sessions!=0
            or old_sqlite_digest!=restored_sqlite_digest
            or not target_absent
            or "PermissionError" not in stderr
            or "Operation not permitted" not in stderr
            or "open(os.devnull" not in stderr
            or "'/dev/null'" not in stderr):
        raise SandboxIncidentBlocked("original OS sandbox redirection blocker not proven")
    return {
        "schema":"local-system-one/phase8_3-h4b-seatbelt-admission-incident-v1",
        "real_native_frozen_source_sha":SOURCE,
        "run_id":RUN_ID,
        "native_child_exit_code":1,
        "native_agent_constructed":False,
        "original_tool_read_file_invoked":False,
        "native_retry_advisory_produced":False,
        "model_provider_physical_attempts":0,
        "shared_stepfun_total_physical_attempts":8,
        "historical_h1_outcome_unknown":1,
        "root_cause":"MACOS_SEATBELT_DENIED_OS_DEVNULL_WRITE_BEFORE_AGENT_CONSTRUCTION",
        "sandbox_policy_deny_worked":True,
        "production_gateway_or_user_files_modified":False,
        "original_local_test_profile_mode":"off",
        "original_test_sqlite_logically_restored":True,
        "original_plugin_and_config_restored":True,
        "isolated_auth_file_metadata_unchanged":True,
        "owned_child_process_groups_stopped":4,
        "raw_test_user_files_and_credentials_exported":False,
        "H4B_real_native_tool_retry_qualification":"NOT_RUN",
        "H4B_scoped_verdict":"BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_UNRESOLVED",
        "original_H4_gateway_case_unchanged":True,
        "automatic_second_H4B_retry_authorized":False,
        "future_guard_fix":"ALLOW_DEV_NULL_ONLY_AND_EXERCISE_OFFICIAL_ONESHOT_PREAMBLE_OFFLINE",
        "active_authority":"NOT_AUTHORIZED",
    }


def verify() -> dict:
    run=PRIVATE/"runs"/RUN_ID
    target=manifest_target(run,expected_case=RUN_ID)
    original=_json(PRIVATE/"runs/h4b_verified.private.json")
    rollback=_json(FINAL_REPORT)
    ownership=inspect_owned()
    provider=audited_snapshot(
        PRIVATE/"provider_real_ledger.private.jsonl",
        new_run=RUN_ID,
    )
    stderrfile=PRIVATE/"logs/h4b_agent.private.log"
    if stderrfile.is_symlink() or not stderrfile.is_file():
        raise SandboxIncidentBlocked("original private H4B native log unavailable")
    stderr=stderrfile.read_text(encoding="utf-8",errors="replace")
    if not POST_DB.is_file() or POST_DB.is_symlink():
        raise SandboxIncidentBlocked("original archived post-native SQLite missing")
    with sqlite3.connect(f"file:{POST_DB.resolve().as_posix()}?mode=ro",
                         uri=True,timeout=4) as conn:
        num=conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE cwd=?",
            (str(run.resolve()),)
        ).fetchone()[0]
    check=inspect_recovery()
    if (check["auth_metadata_unchanged"] is not True
            or check["current_profile_state_matches_before"] is not True
            or check["original_sqlite_digest_matches_before"] is not True
            or yaml.safe_load(CONFIG.read_text())!=isolated_test_config("off")):
        raise SandboxIncidentBlocked("post-run restored test Home has drifted")
    return analyze(
        original,rollback,ownership,provider,stderr=stderr,
        native_sessions=num,
        old_sqlite_digest=_db_digest(PRE_DB),
        restored_sqlite_digest=_db_digest(TEST_HOME/"state.db"),
        target_absent=not target.exists() and not target.is_symlink(),
    )


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write-public",action="store_true")
    opts=p.parse_args()
    try:
        result=verify()
        if opts.write_public:
            if OUTPUT.exists() or OUTPUT.is_symlink():
                raise SandboxIncidentBlocked("H4B incident aggregate already exists")
            OUTPUT.parent.mkdir(parents=True,exist_ok=True)
            OUTPUT.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                              encoding="utf-8")
        print(json.dumps(result,sort_keys=True,indent=2))
    except (SandboxIncidentBlocked,OSError,ValueError,TypeError,
            KeyError,sqlite3.Error):
        print(json.dumps({"status":"BLOCKED",
                          "new_main_provider_requests":0,
                          "no_Agent_invocation_from_this_verifier":True}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
