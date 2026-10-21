#!/usr/bin/env python3
"""Real Hermes H3 native read: System One Runtime unavailable, Shadow fail-open.

One-shot, fail-closed, read-only StepFun Plan experiment. Does not spin up a
decision model Runtime, does not modify production, does not grant Active,
does not reset the 24-physical-request budget or redo H1/H2, and never
imports a token. It uses exactly the NEW authenticated test Home and the
existing append-only Provider ledger. Its built-in observer forwards
Completion to *unbound* 127.0.0.1:18782 and reports real local HTTP 503.

Test Home's unrelated automatic model-generated session title is disabled
in this H3 ONLY; it remains enabled in historical H1/H2 immutable evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time

from phase8_3_prepare_shared_dependency_home import (
    TEST_HOME, inspect, isolated_test_config, set_test_mode,
)
from phase8_3_pin_stepfun_route import inspect as route_inspect
from phase8_3_real_hermes_h2 import (
    ROOT, PRIVATE, MODEL_REVISION, PROVIDER_PORT,
    OBSERVER_PORT, RUNTIME_PORT, PER_CASE_MAX, PHYSICAL_GLOBAL_MAX,
    _git, _private_directory, _check_port_available,
    _spawn, _poll_http, _stop_group, _base_env, _read_jsonl, _read_json,
)
from phase8_3_transport_closeout import (
    audited_snapshot, drain_run, H1_ORIGINAL_SHA256, H2_ORIGINAL_SHA256,
    CloseoutBlocked,
)

RUN_ID="h3_runtime_down"
CASE_DIR=PRIVATE/"runs"/RUN_ID
H3_TIMEOUT=90


class H3Blocked(ValueError):
    """Isolated provider/task/evidence prerequisite failed."""


def _private_history_snapshot() -> dict[str,dict[str,list]]:
    root=TEST_HOME/"plugin-data"
    if root.is_symlink() or not root.is_dir():
        raise H3Blocked("isolated Hermes plugin history directory missing")
    all_states={}
    for state in root.glob("*/state.json"):
        if state.is_symlink():
            raise H3Blocked("test plugin state symlink forbidden")
        obj=_read_json(state)
        all_states[str(state.relative_to(root))]={
            name:list(obj.get(name,[])) for name in (
                "completion_loop_probe_history","completion_shadow_history"
            ) if isinstance(obj.get(name,[]),list)
        }
    if len(all_states)!=1:
        raise H3Blocked("ambiguous new Home plugin state, cannot join native events")
    return all_states


def _adapter_delta(baseline: dict[str,dict[str,list]]) -> list[dict]:
    root=TEST_HOME/"plugin-data"
    observed=[]
    for fname, before in baseline.items():
        path=root/fname
        after=_read_json(path)
        for history in ("completion_loop_probe_history","completion_shadow_history"):
            previous=before.get(history,[])
            current=after.get(history,[])
            if not isinstance(current,list) or (
                len(current)<len(previous) or current[:len(previous)]!=previous
            ):
                raise H3Blocked("native adapter history truncated or reordered")
            for row in current[len(previous):]:
                if not isinstance(row,dict):
                    raise H3Blocked("non-object adapter observation")
                if row.get("mode")!="shadow" or row.get("gate")!="completion":
                    raise H3Blocked("unexpected native Gate observation")
                observed.append({
                    k:row[k] for k in (
                        "gate","native_stage","session_ref","turn_ref",
                        "tool_call_ref","decision_request_ref",
                        "action_status","evidence_status","response_request_id_matches",
                    ) if k in row
                })
    return observed


def _check_setup(sha: str) -> dict:
    if not isinstance(sha,str) or len(sha)!=40 or (
        sha!=_git("rev-parse","HEAD") or _git("status","--porcelain=v1")
    ):
        raise H3Blocked("H3 requires clean frozen SHA before any real Provider traffic")
    _private_directory(PRIVATE)
    for sub in ("runs","logs"):
        _private_directory(PRIVATE/sub)
    if subprocess.run(["git","check-ignore","-q",
        "private/phase8_3_native_real/runs/h3_runtime_down"],cwd=ROOT).returncode!=0:
        raise H3Blocked("H3 sensitive files not covered by Git ignore")
    info=inspect(official_auth=True)
    if info["mode"]!="shadow" or not info["credential_stage_ready"]:
        raise H3Blocked("H3 requires freshly authenticated Shadow test Home")
    if route_inspect()["route_status"]!="PINNED_PROXY":
        raise H3Blocked("StepFun credential route could bypass the budget proxy")
    import yaml
    conf=yaml.safe_load((TEST_HOME/"config.yaml").read_text(encoding="utf-8"))
    if conf!=isolated_test_config("shadow"):
        raise H3Blocked("H3 unrelated background LLM title task is not disabled")
    for port in (RUNTIME_PORT,OBSERVER_PORT,PROVIDER_PORT):
        _check_port_available(port)
    ledger=PRIVATE/"provider_real_ledger.private.jsonl"
    before=audited_snapshot(ledger,new_run=RUN_ID)
    frozen=PRIVATE/"provider_h1_h2_frozen.private.jsonl"
    if (frozen.is_symlink() or not frozen.is_file()
        or hashlib.sha256(frozen.read_bytes()).hexdigest()!=H2_ORIGINAL_SHA256
        or before["reserved_global"]!=6
        or before["reserved_h1"]!=3 or before["reserved_h2"]!=3
        or before["reserved_new"]!=0
        or before["ledger_digest_sha256"]!=H2_ORIGINAL_SHA256
        or before["historic_h1_unresolved"]!=1):
        raise H3Blocked("historical H1/H2 physical budget evidence was altered")
    for target in (
        CASE_DIR,PRIVATE/"runs/h3_verified.private.json",
        PRIVATE/"logs/h3_provider.private.log",
        PRIVATE/"logs/h3_observer.private.log",
        PRIVATE/"logs/h3_native.private.log",
        PRIVATE/"h3_http.private.jsonl",
        PRIVATE/"h3_correlation_key.private.bin",
    ):
        if target.exists() or target.is_symlink():
            raise H3Blocked("H3 is single-shot; refuses any previous evidence")
    return before


def _services(keyfile: Path) -> list[subprocess.Popen]:
    processes=[]
    env=_base_env()
    try:
        observer=_spawn([
            sys.executable,str(ROOT/"scripts/phase8_2a_shadow_proxy.py"),
            "--port",str(OBSERVER_PORT),
            "--destination",f"http://127.0.0.1:{RUNTIME_PORT}",
            "--evidence",str(PRIVATE/"h3_http.private.jsonl"),
            "--run-id",RUN_ID,"--private-key-file",str(keyfile),
        ],PRIVATE/"logs/h3_observer.private.log",env=env)
        processes.append(observer)
        # NEVER launch the MLX Runtime in H3; port 18782 MUST be absent.
        end=time.monotonic()+8
        import socket
        while time.monotonic()<end:
            if observer.poll() is not None:
                raise H3Blocked("H3 local-only Observer could not start")
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
                if sock.connect_ex(("127.0.0.1",OBSERVER_PORT))==0:
                    break
            time.sleep(.15)
        else:raise H3Blocked("H3 observer not listening")
        _check_port_available(RUNTIME_PORT)
        provider=_spawn([
            sys.executable,str(ROOT/"scripts/phase8_2a_provider_cap.py"),
            "--port",str(PROVIDER_PORT),
            "--private-ledger",str(PRIVATE/"provider_real_ledger.private.jsonl"),
            "--run",RUN_ID,"--total-cap",str(PHYSICAL_GLOBAL_MAX),
            "--per-run-cap",str(PER_CASE_MAX),
            "--execute-real-provider",
        ],PRIVATE/"logs/h3_provider.private.log",env=env)
        processes.append(provider)
        status=_poll_http(f"http://127.0.0.1:{PROVIDER_PORT}/_budget",provider,timeout=8)
        if status!={"run":RUN_ID,"used_total":6,"used_run":0,
                    "total_cap":24,"per_run_cap":3}:
            raise H3Blocked("shared physical ledger cap incorrectly reset or widened")
        return processes
    except BaseException:
        for p in reversed(processes):_stop_group(p)
        raise


def _native(sha: str,key: bytes) -> tuple[int,bool]:
    if len(key)!=32:raise H3Blocked("invalid H3 private HMAC key")
    env=_base_env()
    env["LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE"]="isolated-shadow-test-v1"
    env["LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX"]=key.hex()
    cmd=[
        sys.executable,str(ROOT/"scripts/phase8_2a_native_run.py"),
        "--platform","hermes","--mode","shadow",
        "--scenario","read_nonce","--run",RUN_ID,
        "--expected-sha",sha,"--private-root",str(PRIVATE),
        "--hermes-home",str(TEST_HOME),
        "--shadow-log",str(PRIVATE/"h3_http.private.jsonl"),
        "--provider-proxy-port",str(PROVIDER_PORT),
        "--timeout",str(H3_TIMEOUT),
        "--authorize-existing-step-plan",
    ]
    proc=_spawn(cmd,PRIVATE/"logs/h3_native.private.log",env=env)
    try:
        return proc.wait(timeout=H3_TIMEOUT+18),False
    except subprocess.TimeoutExpired:
        _stop_group(proc)
        return proc.returncode or 124,True


def _native_oracle() -> dict:
    file=CASE_DIR/"input.txt"
    db=TEST_HOME/"state.db"
    if not file.is_file() or not db.is_file():
        return {"valid":False,"reason":"native_source_absent"}
    from phase8_2a_hermes_paired_verify import _native_sqlite_evidence
    try:
        token=file.read_bytes().decode("utf-8")
        if not token.startswith("P83_HERMES_NATIVE_") or len(token)<45:
            raise H3Blocked("new independent H3 nonce invalid")
        uri=f"file:{db.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri,uri=True,timeout=4) as sql:
            output=_native_sqlite_evidence(sql,CASE_DIR,token)
        return {
            "valid":all(output.values()),
            "native_tool_call_result_id_paired":output["native_tool_call_result_id_paired"],
            "original_file_bytes_match_tool":output["native_tool_result_matches_original_file"],
            "final_answer_matches_original":output["agent_final_matches_original_file"],
            "nonce_absent_from_prompt":output["hidden_oracle_absent_from_task_prompt"],
            "native_provider_route_confirmed":output["original_provider_route_verified"],
        }
    except (ValueError,TypeError,KeyError,OSError,sqlite3.Error):
        return {"valid":False,"reason":"native_proof_rejected"}


def _correlate_h3(key: bytes, adapter: list[dict], http: list[dict]) -> dict:
    from phase8_2b_native_correlate import correlate
    try:
        outcome=correlate(
            "hermes",TEST_HOME/"state.db",adapter,http,key,
        )
        return {
            "status":outcome["status"],
            "native_http_pairs_verified":outcome["native_http_pairs_verified"],
            "adapter_completion_observations":outcome["adapter_completion_observations"],
            "issues":outcome["issues"],
        }
    except (ValueError,TypeError,OSError,sqlite3.Error):
        return {"status":"BLOCKED","native_http_pairs_verified":0,
                "cause":"strict_hermes_identity_join_failed"}


def run(sha: str) -> dict:
    # OFF/Shadow isolation is an explicit operator step, never changed
    # silently inside a native test's auth/source preflight.
    before=_check_setup(sha)
    baseline=_private_history_snapshot()
    oldmask=os.umask(0o077)
    services=[]
    key=None
    exitcode=None
    timed_out=False
    failure_class=None
    ledger={}
    profile_off_restored=False
    try:
        keyfile=PRIVATE/"h3_correlation_key.private.bin"
        with keyfile.open("xb") as f:
            key=secrets.token_bytes(32)
            f.write(key)
            f.flush()
            os.fsync(f.fileno())
        keyfile.chmod(0o600)
        services=_services(keyfile)
        exitcode,timed_out=_native(sha,key)
        # The native Agent has exited but an unrelated main Provider
        # connection can still be in flight. Wait for its genuine terminal
        # event, never synthesize a missing response.
        ledger=audited_snapshot(
            PRIVATE/"provider_real_ledger.private.jsonl",new_run=RUN_ID)
        if ledger["reserved_new"]:
            ledger=drain_run(
                PRIVATE/"provider_real_ledger.private.jsonl",
                run_id=RUN_ID,maximum_seconds=80,
            )
        # The observer itself has a short bounded follow-through for the
        # asynchronous post-tool hook, with no new native Agent request.
        until=time.monotonic()+7
        while len(_read_jsonl(PRIVATE/"h3_http.private.jsonl"))<2 and time.monotonic()<until:
            time.sleep(.15)
    except BaseException as error:
        failure_class=type(error).__name__
    finally:
        for process in reversed(services):
            _stop_group(process)
        try:
            result=set_test_mode("off")
            profile_off_restored=(result["mode"]=="off")
        except (OSError,ValueError,TypeError):
            profile_off_restored=False
        os.umask(oldmask)

    try:
        ledger=audited_snapshot(
            PRIVATE/"provider_real_ledger.private.jsonl",new_run=RUN_ID,
        )
    except (OSError,ValueError,CloseoutBlocked):
        ledger={"new_run_status":"BLOCKED_LEDGER_INTEGRITY",
                "overall_phase_8_3a_integrity":"BLOCKED"}

    try:
        native=_read_json(CASE_DIR/"verified_summary.private.json")
    except (OSError,ValueError,H3Blocked):
        native={}
    native_evidence=_native_oracle()
    http=_read_jsonl(PRIVATE/"h3_http.private.jsonl")
    try:
        adapter=_adapter_delta(baseline)
    except (H3Blocked,ValueError,OSError):
        adapter=[]
    if key is not None and http and adapter:
        joined=_correlate_h3(key,adapter,http)
    else:
        joined={"status":"NOT_ESTABLISHED","native_http_pairs_verified":0}
    statuses=[x.get("http_status") for x in http]
    backends=[x.get("backend") for x in http]
    decisions=[x.get("decision_source") for x in http]
    flags=[x.get("action_status") for x in adapter]
    # Under a Runtime outage, neither a model result nor an echoed response
    # ID exists; an exact HMAC request/native mapping can still be verified.
    scoped=bool(
        failure_class is None and profile_off_restored
        and exitcode==0 and not timed_out
        and native.get("code_sha")==sha and native.get("run_id")==RUN_ID
        and native.get("mode")=="shadow"
        and native.get("platform")=="hermes"
        and native.get("scenario")=="read_nonce"
        and native.get("input_unchanged") is True
        and native.get("read_proof",{}).get("final_answer_matches_nonce") is True
        and native_evidence.get("valid") is True
        and ledger.get("new_run_status")=="SCOPE_COMPLETE"
        and ledger.get("unknown_new")==0
        and ledger.get("responded_new")==ledger.get("attempted_new")
        and 1 <= ledger.get("attempted_new",0) <= PER_CASE_MAX
        and len(http)==2 and statuses==[503,503]
        and backends==[None,None] and decisions==[None,None]
        and len(adapter)==2 and all(x=="failed_open" for x in flags)
        and joined.get("status")=="PASS"
        and joined.get("native_http_pairs_verified")==2
    )
    uses=native.get("usage",{})
    summary={
        "schema":"local-system-one/phase8_3-h3-native-runtime-down-v1",
        "run_id":RUN_ID,
        "source_sha":sha,
        "platform":"hermes",
        "mode":"shadow",
        "main_model":"stepfun/step-5-preview",
        "laya_runtime":"INTENTIONALLY_DOWN",
        "native_agent_exit_code":exitcode,
        "native_agent_timed_out":timed_out,
        "native_independent_oracle":native_evidence,
        "provider_physical_ledger":{
            key:ledger.get(key) for key in (
                "reserved_global","reserved_h1","reserved_h2","reserved_new",
                "attempted_new","responded_new","unknown_new","finalized_new",
                "new_run_status","historic_h1_unresolved",
                "overall_phase_8_3a_integrity","global_request_limit",
                "per_run_limit","ledger_digest_sha256",
            )
        },
        "agent_reported":{
            k:uses.get(k) for k in ("api_calls","input_tokens",
                                   "output_tokens","completed","failed")
        },
        "observer":{
            "actual_http_statuses":statuses,
            "backends":backends,
            "decision_sources":decisions,
            "new_adapter_events":len(adapter),
            "adapter_action_statuses":flags,
            "native_adapter_http":joined,
        },
        "background_title_llm_upgrade":"DISABLED_TEST_HOME_ONLY",
        "profile_off_restored":profile_off_restored,
        "run_error_class":failure_class,
        "h3_scoped_verdict":"PASS_SCOPED" if scoped else "PARTIAL_OR_BLOCKED",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_REQUEST",
        "actual_stepfun_plan_debit":"UNKNOWN",
        "active_authority":"NOT_AUTHORIZED",
        "no_automated_retry_or_native_action_change":True,
    }
    destination=PRIVATE/"runs/h3_verified.private.json"
    if destination.exists() or destination.is_symlink():
        raise H3Blocked("previous H3 result exists, never overwrite")
    destination.write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n",
                           encoding="utf-8")
    destination.chmod(0o600)
    return summary


def main() -> None:
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--frozen-sha",required=True)
    arg.add_argument("--execute-real-step-plan",action="store_true")
    a=arg.parse_args()
    if not a.execute_real_step_plan:
        arg.error("H3 one-shot Plan request requires explicit previous user authorization")
    try:
        result=run(a.frozen_sha)
        print(json.dumps(result,indent=2,sort_keys=True))
        if result["h3_scoped_verdict"]!="PASS_SCOPED":
            raise SystemExit(3)
    except (H3Blocked,OSError,ValueError,TypeError,subprocess.SubprocessError):
        print(json.dumps({
            "status":"BLOCKED",
            "phase8_3a_overall":"BLOCKED",
            "no_new_provider_requests_from_error_handler":True,
        }))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
