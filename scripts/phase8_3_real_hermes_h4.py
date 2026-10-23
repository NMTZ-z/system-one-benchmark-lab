#!/usr/bin/env python3
"""One-shot H4 real StepFun Hermes Shadow native MISSING-read with Retry proof.

The H1/H2/H3 original 8 physical Provider attempts remain irreversible. This
runner checks the historical digest, the EXACT pinned test Home, the separate
pinned manual credential and source plugin, then starts only isolated local
Laya/MLX (18782), Observer (18793), Provider cap (18794). It runs one native
read_missing, never writes the target, retries it, or alters Agent control.

A native failure PASS requires the actual Hermes SQLite structured error;
a Retry Shadow PASS additionally requires test-only keyed provenance matched
to the same native tool and one real Laya HTTP event. These are distinct.
No real Agent, Provider, or local service starts without --execute-real-step-plan
and an exact clean frozen candidate SHA.
"""
from __future__ import annotations

import argparse
from collections import Counter
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
    TEST_HOME, inspect as home_inspect, isolated_test_config, set_test_mode,
)
from phase8_3_pin_stepfun_route import inspect as route_inspect
from phase8_3_refresh_test_plugin import audit as plugin_audit
from phase8_3_real_hermes_h2 import (
    ROOT, PRIVATE, MODEL_PATH, MODEL_REVISION,
    PROVIDER_PORT, RUNTIME_PORT, OBSERVER_PORT,
    PHYSICAL_GLOBAL_MAX, PER_CASE_MAX,
    _git, _private_directory, _check_port_available,
    _spawn, _poll_http, _stop_group, _base_env, _read_json, _read_jsonl,
)
from phase8_3_transport_closeout import (
    H4, H3_ORIGINAL_SHA256, audited_snapshot, drain_run, CloseoutBlocked,
)
from phase8_3_h4_failure_oracle import (
    check_sqlite_failed_read, NativeH4OracleBlocked,
)
from phase8_3_h4_retry_evidence import (
    verify_retry_exact, RetryEvidenceBlocked,
)

RUN_ID = H4
CASE_DIR = PRIVATE / "runs" / RUN_ID
H4_TIMEOUT = 90


class H4Blocked(ValueError):
    """Preapproved H4 real task conditions are not met."""


def _history_snapshot() -> dict[str,list[dict]]:
    plugin_root=TEST_HOME/"plugin-data"
    if plugin_root.is_symlink() or not plugin_root.is_dir():
        raise H4Blocked("isolated native plugin state not found")
    states=list(plugin_root.glob("*/state.json"))
    if len(states)!=1 or states[0].is_symlink():
        raise H4Blocked("ambiguous isolated native Adapter state files")
    state=_read_json(states[0])
    names=(
        "completion_loop_probe_history","completion_shadow_history",
        "retry_escalation_shadow_history",
    )
    result={}
    for name in names:
        history=state.get(name,[])
        if not isinstance(history,list):
            raise H4Blocked("untrusted original Adapter history type")
        result[name]=history
    return result


def _history_delta(before: dict[str,list[dict]]) -> dict[str,list[dict]]:
    root=TEST_HOME/"plugin-data"
    states=list(root.glob("*/state.json"))
    if len(states)!=1 or states[0].is_symlink():
        raise H4Blocked("original H4 Adapter storage identity changed")
    current=_read_json(states[0])
    result={}
    for name, old in before.items():
        newer=current.get(name,[])
        if not isinstance(newer,list) or newer[:len(old)]!=old:
            raise H4Blocked("prior Adapter history was truncated/changed")
        if len(newer)>len(old)+3:
            raise H4Blocked("unexpected concurrent native Adapter events")
        result[name]=newer[len(old):]
    return result


def _preflight(frozen_sha: str) -> dict:
    if (
        not isinstance(frozen_sha,str) or len(frozen_sha)!=40
        or _git("rev-parse","HEAD")!=frozen_sha
        or _git("status","--porcelain=v1")
    ):
        raise H4Blocked("H4 real task requires exactly frozen clean committed SHA")
    if (not PRIVATE.is_dir() or PRIVATE.is_symlink()
            or PRIVATE.stat().st_mode & 0o077):
        raise H4Blocked("original isolated research root is not private")
    for name in ("runs","logs"):
        _private_directory(PRIVATE/name)
    if subprocess.run(
        ["git","check-ignore","-q","private/phase8_3_native_real/runs/h4_missing_read"],
        cwd=ROOT,check=False,
    ).returncode!=0:
        raise H4Blocked("H4 private evidence files not ignored by Git")
    info=home_inspect(official_auth=True)
    if info["mode"]!="shadow" or not info["credential_stage_ready"]:
        raise H4Blocked("isolated Hermes H4 must be authenticated Shadow-only")
    if route_inspect().get("route_status")!="PINNED_PROXY":
        raise H4Blocked("isolated credential could bypass Provider cap")
    if not plugin_audit(apply=False)["new_isolated_plugin_matches_frozen_commit"]:
        raise H4Blocked("H4 plugin source differs from frozen reviewed Git")
    import yaml
    cfg=yaml.safe_load((TEST_HOME/"config.yaml").read_text(encoding="utf-8"))
    if cfg!=isolated_test_config("shadow"):
        raise H4Blocked("test Home not strict non-active Shadow; title LLM still enabled")
    if not MODEL_PATH.is_dir() or not (MODEL_PATH/"rl_agent_config.json").is_file():
        raise H4Blocked("pinned local MLX decision model missing")
    for port in (RUNTIME_PORT,OBSERVER_PORT,PROVIDER_PORT):
        _check_port_available(port)
    previous=audited_snapshot(
        PRIVATE/"provider_real_ledger.private.jsonl",new_run=RUN_ID)
    archived=PRIVATE/"provider_h1_h2_h3_frozen.private.jsonl"
    if (
        archived.is_symlink() or not archived.is_file()
        or hashlib.sha256(archived.read_bytes()).hexdigest()!=H3_ORIGINAL_SHA256
        or previous["reserved_global"]!=8
        or previous["reserved_h1"]!=3
        or previous["reserved_h2"]!=3
        or previous["reserved_h3"]!=2
        or previous["reserved_new"]!=0
        or previous["ledger_digest_sha256"]!=H3_ORIGINAL_SHA256
        or previous["historic_h1_unresolved"]!=1
    ):
        raise H4Blocked("original H1+H2+H3 Provider history altered")
    for path in (
        CASE_DIR,
        PRIVATE/"runs/h4_verified.private.json",
        PRIVATE/"logs/h4_runtime.private.log",
        PRIVATE/"logs/h4_observer.private.log",
        PRIVATE/"logs/h4_provider.private.log",
        PRIVATE/"logs/h4_native.private.log",
        PRIVATE/"h4_http.private.jsonl",
        PRIVATE/"h4_correlation_key.private.bin",
    ):
        if path.exists() or path.is_symlink():
            raise H4Blocked("H4 is one-shot; refuse existing attempted evidence")
    if not (TEST_HOME/"state.db").is_file():
        raise H4Blocked("isolated historical Hermes native state store unavailable")
    return previous


def _services(correlation_key_file: Path) -> list[subprocess.Popen]:
    env=_base_env()
    py=sys.executable
    start=[]
    try:
        runtime=_spawn([
            py,"-m","local_system_one",
            "--source",str(MODEL_PATH),"--host","127.0.0.1",
            "--port",str(RUNTIME_PORT),
        ],PRIVATE/"logs/h4_runtime.private.log",env=env)
        start.append(runtime)
        _poll_http(f"http://127.0.0.1:{RUNTIME_PORT}/health",runtime,timeout=40)
        observer=_spawn([
            py,str(ROOT/"scripts/phase8_2a_shadow_proxy.py"),
            "--port",str(OBSERVER_PORT),
            "--destination",f"http://127.0.0.1:{RUNTIME_PORT}",
            "--evidence",str(PRIVATE/"h4_http.private.jsonl"),
            "--run-id",RUN_ID,
            "--private-key-file",str(correlation_key_file),
        ],PRIVATE/"logs/h4_observer.private.log",env=env)
        start.append(observer)
        import socket
        cutoff=time.monotonic()+8
        while time.monotonic()<cutoff:
            if observer.poll() is not None:
                raise H4Blocked("isolated Completion/Retry Observer failed")
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1",OBSERVER_PORT))==0:
                    break
            time.sleep(.1)
        else:
            raise H4Blocked("isolated Observer not listening")
        provider=_spawn([
            py,str(ROOT/"scripts/phase8_2a_provider_cap.py"),
            "--port",str(PROVIDER_PORT),
            "--private-ledger",str(PRIVATE/"provider_real_ledger.private.jsonl"),
            "--run",RUN_ID,
            "--total-cap",str(PHYSICAL_GLOBAL_MAX),
            "--per-run-cap",str(PER_CASE_MAX),
            "--execute-real-provider",
        ],PRIVATE/"logs/h4_provider.private.log",env=env)
        start.append(provider)
        budget=_poll_http(f"http://127.0.0.1:{PROVIDER_PORT}/_budget",provider,timeout=8)
        if budget!={"run":RUN_ID,"used_total":8,"used_run":0,
                    "total_cap":24,"per_run_cap":3}:
            raise H4Blocked("live physical Provider proxy cap/history wrong")
        return start
    except BaseException:
        for p in reversed(start):
            _stop_group(p)
        raise


def _native(frozen_sha: str, key: bytes) -> tuple[int,bool]:
    if len(key)!=32:
        raise H4Blocked("test-only H4 keyed evidence malformed")
    env=_base_env()
    env["LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE"]="isolated-shadow-test-v1"
    env["LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX"]=key.hex()
    cmd=[
        sys.executable,str(ROOT/"scripts/phase8_2a_native_run.py"),
        "--platform","hermes","--mode","shadow",
        "--scenario","read_missing",
        "--run",RUN_ID,
        "--expected-sha",frozen_sha,
        "--private-root",str(PRIVATE),
        "--hermes-home",str(TEST_HOME),
        "--shadow-log",str(PRIVATE/"h4_http.private.jsonl"),
        "--provider-proxy-port",str(PROVIDER_PORT),
        "--timeout",str(H4_TIMEOUT),
        "--authorize-existing-step-plan",
    ]
    process=_spawn(cmd,PRIVATE/"logs/h4_native.private.log",env=env)
    try:
        return process.wait(timeout=H4_TIMEOUT+18),False
    except subprocess.TimeoutExpired:
        _stop_group(process)
        return process.returncode or 124,True


def _sanitize_adapter(records: list[dict], *, gate: str) -> list[dict]:
    allow=(
        "gate","mode","native_stage","session_ref","turn_ref",
        "tool_call_ref","decision_request_ref","request_id",
        "response_request_id_matches","evidence_status",
        "action_status","action_reason","decision",
    )
    filtered=[]
    for row in records:
        if not isinstance(row,dict) or row.get("gate")!=gate:
            raise H4Blocked("untrusted H4 private Adapter event")
        filtered.append({name:row[name] for name in allow if name in row})
    return filtered


def _completion_links(key: bytes, adapter: list[dict], http: list[dict]) -> dict:
    from phase8_2b_native_correlate import correlate
    try:
        result=correlate(
            "hermes",TEST_HOME/"state.db",adapter,http,key,
        )
        return {
            "status":result["status"],
            "pairs":result["native_http_pairs_verified"],
            "adapter_observations":result["adapter_completion_observations"],
            "issues":result["issues"],
        }
    except (ValueError,TypeError,OSError,sqlite3.Error):
        return {"status":"BLOCKED","pairs":0,"issues":["strict_identity_join_failed"]}


def run(frozen_sha: str) -> dict:
    previous=_preflight(frozen_sha)
    before=_history_snapshot()
    mask=os.umask(0o077)
    services=[]
    correlation_key=None
    native_exit=None
    native_timeout=False
    failure=None
    restored_off=False
    try:
        keyfile=PRIVATE/"h4_correlation_key.private.bin"
        with keyfile.open("xb") as output:
            correlation_key=secrets.token_bytes(32)
            output.write(correlation_key)
            output.flush()
            os.fsync(output.fileno())
        keyfile.chmod(0o600)
        services=_services(keyfile)
        native_exit,native_timeout=_native(frozen_sha,correlation_key)
        ledger=audited_snapshot(
            PRIVATE/"provider_real_ledger.private.jsonl",new_run=RUN_ID)
        if ledger["reserved_new"]:
            ledger=drain_run(
                PRIVATE/"provider_real_ledger.private.jsonl",
                run_id=RUN_ID,maximum_seconds=80,
            )
        deadline=time.monotonic()+9
        while time.monotonic()<deadline:
            if len(_read_jsonl(PRIVATE/"h4_http.private.jsonl"))>=3:
                break
            time.sleep(.2)
    except BaseException as exc:
        failure=type(exc).__name__
    finally:
        for process in reversed(services):
            _stop_group(process)
        try:
            restoration=set_test_mode("off")
            restored_off=restoration["mode"]=="off"
        except (OSError,ValueError,TypeError):
            restored_off=False
        os.umask(mask)
    try:
        current=audited_snapshot(
            PRIVATE/"provider_real_ledger.private.jsonl",new_run=RUN_ID)
    except (CloseoutBlocked,OSError,ValueError):
        current={"new_run_status":"BLOCKED_LEDGER_INTEGRITY"}
    try:
        native=_read_json(CASE_DIR/"verified_summary.private.json")
    except (OSError,ValueError):
        native={}
    try:
        oracle=check_sqlite_failed_read(TEST_HOME/"state.db",CASE_DIR)
    except (NativeH4OracleBlocked,sqlite3.Error,ValueError,OSError):
        oracle={"native_result_structured_missing_file":False,"status":"NOT_VERIFIED"}
    try:
        delta=_history_delta(before)
    except (ValueError,OSError,H4Blocked):
        delta={}
    completion=[
        *_sanitize_adapter(delta.get("completion_loop_probe_history",[]),gate="completion"),
        *_sanitize_adapter(delta.get("completion_shadow_history",[]),gate="completion"),
    ] if delta else []
    retries=_sanitize_adapter(
        delta.get("retry_escalation_shadow_history",[]),gate="retry_escalation"
    ) if delta else []
    http=_read_jsonl(PRIVATE/"h4_http.private.jsonl")
    completion_http=[row for row in http
                     if row.get("path")=="/v1/workflows/completion-gate"]
    if correlation_key is not None and completion and completion_http:
        cjoin=_completion_links(correlation_key,completion,completion_http)
    else:
        cjoin={"status":"NOT_ESTABLISHED","pairs":0}
    if correlation_key is not None and retries and completion and http:
        try:
            rjoin=verify_retry_exact(
                TEST_HOME/"state.db",CASE_DIR,correlation_key,
                retry_adapter=retries,completion_adapter=completion,http=http,
            )
        except (RetryEvidenceBlocked,ValueError,sqlite3.Error,OSError):
            rjoin={"status":"BLOCKED","native_retry_tool_hmac_match":False}
    else:
        rjoin={"status":"NOT_ESTABLISHED","native_retry_tool_hmac_match":False}
    physical_pass=bool(
        current.get("new_run_status")=="SCOPE_COMPLETE"
        and current.get("reserved_h1")==3
        and current.get("reserved_h2")==3
        and current.get("reserved_h3")==2
        and current.get("historic_h1_unresolved")==1
        and 1<=current.get("attempted_new",0)<=3
        and current.get("attempted_new")==current.get("responded_new")
        ==current.get("finalized_new")==current.get("reserved_new")
        and current.get("unknown_new")==0
    )
    tool_pass=bool(
        native_exit==0 and native_timeout is False
        and native.get("code_sha")==frozen_sha
        and native.get("run_id")==RUN_ID
        and native.get("mode")=="shadow"
        and native.get("scenario")=="read_missing"
        and native.get("h4_missing_file_absent") is True
        and oracle.get("native_result_structured_missing_file") is True
        and oracle.get("tool_calls_exactly_one") is True
    )
    completion_pass=bool(
        len(completion)==2 and len(completion_http)==2
        and all(x.get("http_status")==200 and x.get("backend")=="mlx"
                and x.get("response_matches_request_id") is True
                for x in completion_http)
        and cjoin.get("status")=="PASS" and cjoin.get("pairs")==2
    )
    retry_pass=bool(
        rjoin.get("native_retry_tool_hmac_match") is True
        and len(retries)==1
        and retries[0].get("action_status")=="observed"
    )
    overall=(
        "PASS_SCOPED" if (
            failure is None and restored_off and tool_pass
            and physical_pass and completion_pass and retry_pass
        ) else "PARTIAL_OR_BLOCKED"
    )
    result={
        "schema":"local-system-one/phase8_3-real-h4-native-missing-read-v1",
        "run_id":RUN_ID,"source_sha":frozen_sha,
        "main_model":"stepfun/step-5-preview","platform":"hermes",
        "mode":"shadow","laya_backend":"mlx",
        "native_agent_exit_code":native_exit,
        "native_agent_timed_out":native_timeout,
        "native_tool_failure_oracle":oracle,
        "completion_native_http":{
            "status":cjoin.get("status"),"verified_pairs":cjoin.get("pairs"),
            "real_http_count":len(completion_http),
        },
        "retry_shadow":{
            "real_adapter_events":len(retries),
            "native_failed_read_request_hmac_join":rjoin,
            "observed_decisions":[x.get("decision") for x in retries],
            "no_auto_retry_authority":True,
        },
        "physical_provider":{
            k:current.get(k) for k in (
                "reserved_global","reserved_h1","reserved_h2","reserved_h3",
                "reserved_new","attempted_new","responded_new","unknown_new",
                "finalized_new","new_run_status","historic_h1_unresolved",
                "overall_phase_8_3a_integrity","ledger_digest_sha256",
            )
        },
        "native_reported_api_calls":native.get("usage",{}).get("api_calls"),
        "provider_credit_debit":"UNKNOWN",
        "actual_billing_savings":"NOT_MEASURED",
        "agent_final_truthfulness":"NOT_AUTOMATICALLY_VERIFIED",
        "profile_restored_off":restored_off,
        "real_run_failure_class":failure,
        "h4_tool_native_outcome":"PASS" if tool_pass else "NOT_VERIFIED",
        "h4_completion_observation":"PASS" if completion_pass else "NOT_VERIFIED",
        "h4_retry_observation":"PASS" if retry_pass else "NOT_VERIFIED",
        "h4_physical_accounting":"PASS" if physical_pass else "NOT_VERIFIED",
        "h4_scoped_verdict":overall,
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_REQUEST",
        "active_authority":"NOT_AUTHORIZED",
        "real_h4_auto_retry_attempts":0 if oracle.get("tool_calls_exactly_one") is True else None,
    }
    private=PRIVATE/"runs/h4_verified.private.json"
    if private.exists() or private.is_symlink():
        raise H4Blocked("single H4 evidence cannot be overwritten")
    private.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                       encoding="utf-8")
    private.chmod(0o600)
    return result


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frozen-sha",required=True)
    ap.add_argument("--execute-real-step-plan",action="store_true")
    args=ap.parse_args()
    if not args.execute_real_step_plan:
        ap.error("H4 native Provider run requires explicit existing-plan authorization")
    try:
        result=run(args.frozen_sha)
        print(json.dumps(result,sort_keys=True,indent=2))
        if result["h4_scoped_verdict"]!="PASS_SCOPED":
            raise SystemExit(3)
    except (H4Blocked,ValueError,TypeError,OSError,subprocess.SubprocessError):
        print(json.dumps({"status":"BLOCKED",
                          "real_h4_provider_usage":"UNKNOWN_IF_ATTEMPTED",
                          "active_authority":"NOT_AUTHORIZED"}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
