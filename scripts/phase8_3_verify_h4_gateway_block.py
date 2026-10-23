#!/usr/bin/env python3
"""H4 false-success prevention: read-only adjudication of a gateway admission block.

The original H4 invocation attempted to start an isolated Hermes Agent.
The host already had one live, production-owned Gateway; the new test
Home was not a served profile. Native Hermes therefore EXITED BEFORE
a tool call or main Provider request. It is NOT a failed native file
task, not Retry Shadow and not a real 8.3A H4 PASS.

Never retry here, fix the original evidence, access tokens, start a gateway,
or touch the H1/H2/H3 physical ledger. Output is allowlisted aggregate ONLY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from phase8_3_h4_failure_oracle import manifest_target
from phase8_3_transport_closeout import (
    H3_ORIGINAL_SHA256, audited_snapshot, H4,
)
from phase8_3_real_hermes_h2 import PRIVATE, ROOT, TEST_HOME

FROZEN_H4="a32eb078593cb4a9139c9aa181d017b9bb010298"
OUTPUT=ROOT/"results/processed/phase8_3_h4_gateway_admission_blocked.json"


class H4AdmissionBlocked(ValueError):
    pass


def analyze(native: dict, outer: dict, *,
            provider_sha: str, native_sessions: int,
            gateway_stderr: str, observer_exists: bool,
            original_absent: bool) -> dict:
    if (native.get("code_sha")!=FROZEN_H4 or native.get("run_id")!=H4
            or native.get("mode")!="shadow" or native.get("scenario")!="read_missing"
            or native.get("platform")!="hermes"):
        raise H4AdmissionBlocked("original H4 source/case is not authenticated")
    if (native.get("process_exit_code")!=1
            or native.get("provider_calls_counted_at_proxy")!=0
            or native.get("h4_missing_file_absent") is not True
            or native.get("usage")!={}
            or native.get("timed_out") is not False):
        raise H4AdmissionBlocked("H4 native process/usage does not match admission block")
    if (outer.get("source_sha")!=FROZEN_H4
            or outer.get("run_id")!=H4
            or outer.get("native_agent_exit_code")!=0
            or outer.get("h4_scoped_verdict")!="PARTIAL_OR_BLOCKED"
            or outer.get("profile_restored_off") is not True
            or outer.get("physical_provider",{}).get("reserved_new")!=0):
        raise H4AdmissionBlocked("original outer runner's process status not preserved")
    if (provider_sha!=H3_ORIGINAL_SHA256 or native_sessions!=0
            or observer_exists or not original_absent
            or "Gateway could not start" not in gateway_stderr
            or "host gateway already serves profile" not in gateway_stderr):
        raise H4AdmissionBlocked("original Gateway refusal or no-provider trace not established")
    return {
        "schema":"local-system-one/phase8_3-h4-gateway-admission-incident-v1",
        "frozen_real_runner_source_sha":FROZEN_H4,
        "case":H4,
        "hermes_mode":"shadow",
        "original_hermes_process_exit":1,
        "original_wrapper_process_exit":0,
        "wrapper_misreported_agent_failure":True,
        "root_cause":"RUNNER_USES_GATEWAY_BACKED_CLI_WHILE_HOST_GATEWAY_ALREADY_OWNS_OTHER_PROFILES",
        "actual_native_session_created":False,
        "actual_native_read_file_invoked":False,
        "actual_native_retry_observed":False,
        "real_provider_physical_attempts_h4":0,
        "provider_ledger_global_reserved":8,
        "provider_ledger_original_sha256":H3_ORIGINAL_SHA256,
        "historical_H1_unresolved":1,
        "original_test_missing_target_still_absent":True,
        "isolation_test_home_restored_off":True,
        "h4_status":"BLOCKED_BEFORE_NATIVE_AGENT_AND_PROVIDER",
        "h4_real_stepfun_native_failure_qualification":"NOT_RUN",
        "automatic_h4_rerun_permitted":False,
        "active_authority":"NOT_AUTHORIZED",
        "subscription_credit_spend_for_h4":"NO_PROVIDER_REQUEST_OBSERVED",
        "production_gateway_modified":False,
        "gateway_compatibility_followup":"CHECK_OFFICIAL_IN_PROCESS_HERMES_AGENT_ENTRY_OFFLINE",
    }


def verify() -> dict:
    root=PRIVATE
    target=root/"runs"/H4
    manifest_target(target)
    native_path=target/"verified_summary.private.json"
    outer_path=root/"runs/h4_verified.private.json"
    ledger_path=root/"provider_real_ledger.private.jsonl"
    stderr_path=target/"stderr.private.txt"
    for p in (native_path,outer_path,ledger_path,stderr_path):
        if p.is_symlink() or not p.is_file():
            raise H4AdmissionBlocked("original private H4 evidence is missing or symlinked")
    native=json.loads(native_path.read_text(encoding="utf-8"))
    outer=json.loads(outer_path.read_text(encoding="utf-8"))
    stderr=stderr_path.read_text(errors="replace")
    digest=hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    global_state=audited_snapshot(ledger_path,new_run=H4)
    if global_state["reserved_global"]!=8 or global_state["reserved_new"]!=0:
        raise H4AdmissionBlocked("a physical Provider request was made in H4")
    with sqlite3.connect(
        f"file:{(TEST_HOME/'state.db').resolve().as_posix()}?mode=ro",
        uri=True,timeout=4,
    ) as db:
        native_count=db.execute(
            "SELECT COUNT(*) FROM sessions WHERE cwd=?",
            (str(target.resolve()),)
        ).fetchone()[0]
    return analyze(
        native,outer,provider_sha=digest,native_sessions=native_count,
        gateway_stderr=stderr,
        observer_exists=(root/"h4_http.private.jsonl").exists(),
        original_absent=True,
    )


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--write-public-aggregate",action="store_true")
    opts=cli.parse_args()
    try:
        result=verify()
        if opts.write_public_aggregate:
            if OUTPUT.exists() or OUTPUT.is_symlink():
                raise H4AdmissionBlocked("original incident aggregate cannot be overwritten")
            OUTPUT.parent.mkdir(parents=True,exist_ok=True)
            OUTPUT.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                              encoding="utf-8")
        print(json.dumps(result,sort_keys=True,indent=2))
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):
        print(json.dumps({"status":"BLOCKED",
                          "new_Provider_calls_from_this_verifier":0}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
