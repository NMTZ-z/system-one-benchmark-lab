#!/usr/bin/env python3
"""ONE-SHOT real StepFun Hermes H2 Shadow + local Laya/MLX qualification.

No uncapped Provider calls, no production Home access, no Active authority.
A frozen clean candidate, manually authenticated fresh Hermes Home, exact
Provider URL, original H1 ledger prefix, one H2 physical budget, local
model-only runtime and independently checked native tool/HTTP evidence are
preconditions. The existing H1 UNKNOWN provider attempt remains UNKNOWN.

The script may launch exactly ONE 90-second native read-only H2 task, and
never repeats that task on errors. Raw output stays under ignored private/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError

from phase8_3_real_hermes_pilot import (
    PRIVATE, ROOT, TEST_HOME, _git, _independent_native_proof as _h1_proof,
    _private_directory, _stop_group, PHYSICAL_GLOBAL_MAX, PER_CASE_MAX,
)
from phase8_3_transport_closeout import (
    audited_snapshot, drain_run, CloseoutBlocked,
    H1_ORIGINAL_SHA256,
)
from phase8_3_prepare_shared_dependency_home import inspect as auth_inspect
from phase8_3_pin_stepfun_route import inspect as route_inspect

RUN_ID="h2_read_shadow"
PROVIDER_PORT=18794
RUNTIME_PORT=18782
OBSERVER_PORT=18793
MODEL_REVISION="f9ab0b228f0fc0f14d873dbc99038f135c2da1b2"
MODEL_PATH=(Path.home()/".cache/huggingface/hub/models--convaiinnovations--laya-typed-decisions"
            /"snapshots"/MODEL_REVISION)
H2_NATIVE_TIMEOUT=90
ALLOWED_PORTS=(PROVIDER_PORT,RUNTIME_PORT,OBSERVER_PORT)


class H2Blocked(ValueError):
    pass


def _check_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
        s.settimeout(.4)
        if s.connect_ex(("127.0.0.1",port))==0:
            raise H2Blocked("test-only loopback port already occupied")


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise H2Blocked("private evidence document missing or symlinked")
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict):
        raise H2Blocked("private evidence must be a JSON object")
    return obj


def _check_setup(sha: str) -> dict:
    if len(sha)!=40 or sha!=_git("rev-parse","HEAD") or _git("status","--porcelain=v1"):
        raise H2Blocked("real H2 requires pinned clean committed source")
    if not PRIVATE.is_dir() or PRIVATE.is_symlink():
        raise H2Blocked("isolated ignored test root missing")
    _private_directory(PRIVATE)
    ignored=subprocess.run(["git","check-ignore","-q",
        "private/phase8_3_native_real/runs/h2_read_shadow"],cwd=ROOT,check=False)
    if ignored.returncode!=0:
        raise H2Blocked("H2 evidence is not Git-ignored")
    auth=auth_inspect(official_auth=True)
    if auth.get("mode")!="shadow" or not auth.get("credential_stage_ready"):
        raise H2Blocked("Hermes H2 mode must be Shadow with separately verified auth")
    if route_inspect().get("route_status")!="PINNED_PROXY":
        raise H2Blocked("manual StepFun credential URL not pinned to capped proxy")
    if (not MODEL_PATH.is_dir() or MODEL_PATH.is_symlink() or
        not (MODEL_PATH/"rl_agent_config.json").is_file()):
        raise H2Blocked("pinned cached local MLX decision model missing")
    for port in ALLOWED_PORTS:
        _check_port_available(port)
    for d in ("runs","logs"):
        path=PRIVATE/d
        if not path.is_dir():
            raise H2Blocked("private test subdirectory missing")
        _private_directory(path)
    # Only the exact frozen historical budget ledger is eligible for a NEW
    # run. It has 3 H1 physical reservations, including one unresolved.
    ledger=PRIVATE/"provider_real_ledger.private.jsonl"
    previous=audited_snapshot(ledger,new_run=RUN_ID)
    if (previous["reserved_global"]!=3 or previous["reserved_new"]!=0
        or previous["historic_h1_unresolved"]!=1
        or previous["ledger_digest_sha256"]!=H1_ORIGINAL_SHA256):
        raise H2Blocked("original H1 ledger changed; no authorization to reset 24-call total")
    files=(
        PRIVATE/"runs"/RUN_ID,
        PRIVATE/"runs"/"h2_verified.private.json",
        PRIVATE/"logs"/"h2_runtime.private.log",
        PRIVATE/"logs"/"h2_observer.private.log",
        PRIVATE/"logs"/"h2_provider.private.log",
        PRIVATE/"logs"/"h2_agent.private.log",
        PRIVATE/"h2_correlation_key.private.bin",
        PRIVATE/"h2_http.private.jsonl",
        PRIVATE/"h2_correlation.private.json",
    )
    if any(x.exists() or x.is_symlink() for x in files):
        raise H2Blocked("H2 has already been attempted or contains preexisting logs")
    if not (TEST_HOME/"state.db").is_file():
        raise H2Blocked("expected one previous isolated H1 Hermes native state file")
    return previous


def _spawn(cmd: list[str], outfile: Path, *, env: dict[str,str]) -> subprocess.Popen:
    if outfile.is_symlink() or outfile.exists():
        raise H2Blocked("refuse to overwrite existing test process log")
    with outfile.open("x",encoding="utf-8") as log:
        proc=subprocess.Popen(cmd,cwd=ROOT,env=env,
                              stdin=subprocess.DEVNULL,
                              stdout=log,stderr=subprocess.STDOUT,
                              start_new_session=True)
    return proc


def _poll_http(url: str, proc: subprocess.Popen, *, timeout: float=25) -> dict:
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if proc.poll() is not None:
            raise H2Blocked("isolated loopback test service terminated before ready")
        try:
            with urlopen(url,timeout=1.5) as resp:
                if resp.status!=200:
                    raise H2Blocked("unexpected local service health response")
                value=json.load(resp)
                if not isinstance(value,dict):
                    raise H2Blocked("unexpected local health schema")
                return value
        except (URLError,TimeoutError,ConnectionError,OSError,ValueError):
            time.sleep(.25)
    raise H2Blocked("isolated test service not ready within bounded deadline")


def _base_env() -> dict[str,str]:
    # Avoid inheriting ANY Provider token or production Agent home.
    return {
        "HOME":str(Path.home()),
        "PATH":os.environ.get("PATH","/opt/homebrew/bin:/usr/bin:/bin"),
        "LANG":"en_US.UTF-8",
        "NO_PROXY":"127.0.0.1,localhost",
        "HERMES_DISABLE_LAZY_INSTALLS":"1",
    }


def _service_start(sha: str, corrkey: Path) -> list[subprocess.Popen]:
    base=_base_env()
    logs=PRIVATE/"logs"
    py=sys.executable
    started=[]
    try:
        runtime=_spawn([
            py,"-m","local_system_one",
            "--source",str(MODEL_PATH),
            "--host","127.0.0.1","--port",str(RUNTIME_PORT),
        ],logs/"h2_runtime.private.log",env=base)
        started.append(runtime)
        _poll_http(f"http://127.0.0.1:{RUNTIME_PORT}/health",runtime,timeout=35)
        # Exact HMAC key file holds only ephemeral random bytes; it is not
        # a Provider API key and never enters version control or public JSON.
        observer=_spawn([
            py,str(ROOT/"scripts/phase8_2a_shadow_proxy.py"),
            "--port",str(OBSERVER_PORT),
            "--destination",f"http://127.0.0.1:{RUNTIME_PORT}",
            "--evidence",str(PRIVATE/"h2_http.private.jsonl"),
            "--run-id",RUN_ID,
            "--private-key-file",str(corrkey),
        ],logs/"h2_observer.private.log",env=base)
        started.append(observer)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if observer.poll() is not None:
                raise H2Blocked("observer process failed before readiness")
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1",OBSERVER_PORT))==0:
                    break
            time.sleep(.15)
        else: raise H2Blocked("observer transport not listening")
        # The same durable ledger is reused; the H1 prefix is not
        # shortened/refunded, so global budget arithmetic starts at 3/24.
        provider=_spawn([
            py,str(ROOT/"scripts/phase8_2a_provider_cap.py"),
            "--port",str(PROVIDER_PORT),
            "--private-ledger",str(PRIVATE/"provider_real_ledger.private.jsonl"),
            "--run",RUN_ID,"--total-cap",str(PHYSICAL_GLOBAL_MAX),
            "--per-run-cap",str(PER_CASE_MAX),"--execute-real-provider",
        ],logs/"h2_provider.private.log",env=base)
        started.append(provider)
        budget=_poll_http(f"http://127.0.0.1:{PROVIDER_PORT}/_budget",provider,timeout=8)
        if budget!={"run":RUN_ID,"used_total":3,"used_run":0,
                    "total_cap":24,"per_run_cap":3}:
            raise H2Blocked("existing H1 global physical budget or new H2 cap not attested")
        return started
    except BaseException:
        for p in reversed(started):
            _stop_group(p)
        raise


def _native(sha: str, key: bytes) -> tuple[int,bool]:
    if len(key)!=32:
        raise H2Blocked("invalid private HMAC correlation secret")
    safe=_base_env()
    safe.update({
        "LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE":"isolated-shadow-test-v1",
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX":key.hex(),
    })
    command=[
        sys.executable,str(ROOT/"scripts/phase8_2a_native_run.py"),
        "--platform","hermes","--mode","shadow",
        "--scenario","read_nonce",
        "--run",RUN_ID,"--expected-sha",sha,
        "--private-root",str(PRIVATE),
        "--hermes-home",str(TEST_HOME),
        "--shadow-log",str(PRIVATE/"h2_http.private.jsonl"),
        "--provider-proxy-port",str(PROVIDER_PORT),
        "--timeout",str(H2_NATIVE_TIMEOUT),
        "--authorize-existing-step-plan",
    ]
    proc=_spawn(command,PRIVATE/"logs/h2_agent.private.log",env=safe)
    try:
        return proc.wait(timeout=H2_NATIVE_TIMEOUT+18),False
    except subprocess.TimeoutExpired:
        _stop_group(proc)
        return proc.returncode or 124,True


def _read_jsonl(path: Path) -> list[dict]:
    if path.is_symlink() or not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _plugin_observations() -> list[dict]:
    # Hermes' registered plugin captures only bounded, privacy-safe
    # decision/event metadata. Never export raw tool results from SQLite.
    root=TEST_HOME/"plugin-data"
    if not root.is_dir():
        return []
    records=[]
    for path in root.glob("*/state.json"):
        data=_read_json(path)
        for name in ("completion_shadow_history","completion_loop_probe_history"):
            for row in data.get(name,[]) if isinstance(data.get(name,[]),list) else []:
                if row.get("mode")=="shadow" and row.get("decision_request_ref"):
                    records.append({
                        k:row[k] for k in (
                            "gate","native_stage","session_ref","turn_ref",
                            "tool_call_ref","decision_request_ref",
                            "action_status","evidence_status",
                            "response_request_id_matches",
                        ) if k in row
                    })
    return records


def _native_oracle() -> dict:
    folder=PRIVATE/"runs"/RUN_ID
    noncefile=folder/"input.txt"
    db=TEST_HOME/"state.db"
    if not noncefile.is_file() or not db.is_file():
        return {"valid":False,"reason":"native_state_or_input_not_found"}
    from phase8_2a_hermes_paired_verify import _native_sqlite_evidence
    try:
        value=noncefile.read_bytes().decode("utf-8")
        if not value.startswith("P83_HERMES_NATIVE_") or len(value)<45:
            return {"valid":False,"reason":"H2 unique hidden fixture absent"}
        with sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro",
                             uri=True,timeout=3) as conn:
            proof=_native_sqlite_evidence(conn,folder,value)
        return {
            "valid":all(proof.values()),
            "native_tool_call_result_identity":proof["native_tool_call_result_id_paired"],
            "tool_bytes_match_original":proof["native_tool_result_matches_original_file"],
            "agent_answer_matches_original":proof["agent_final_matches_original_file"],
            "input_absent_from_prompt":proof["hidden_oracle_absent_from_task_prompt"],
            "native_provider_proxy_route":proof["original_provider_route_verified"],
        }
    except (ValueError,sqlite3.Error,KeyError,OSError):
        return {"valid":False,"reason":"independent_native_oracle_failed"}


def _native_http_correlate(key: bytes, http: list[dict]) -> dict:
    from phase8_2b_native_correlate import correlate
    # This H2 test Home is intentionally reused by later H3/H4 studies.
    # For historical re-verification, select ONLY records that prove
    # membership in the original immutable H2 HTTP request-ref set.
    # The deeper join still cryptographically checks each with this
    # run's private key and native SQLite tool/session identity.
    refs=[r.get("decision_request_ref") for r in http]
    if (len(refs)!=2 or any(not isinstance(r,str) or len(r)!=32 for r in refs)
            or len(set(refs))!=len(refs)):
        return {"status":"BLOCKED","native_http_pairs_verified":0,
                "cause":"original_H2_HTTP_reference_set_invalid"}
    all_observed=_plugin_observations()
    adapter=[r for r in all_observed if r.get("decision_request_ref") in set(refs)]
    if (len(adapter)!=2 or len({r.get("decision_request_ref") for r in adapter})!=2):
        return {"status":"BLOCKED","native_http_pairs_verified":0,
                "cause":"missing_or_duplicate_H2_adapter_reference"}
    try:
        r=correlate("hermes",TEST_HOME/"state.db",adapter,http,key)
    except (ValueError,TypeError,sqlite3.Error,OSError):
        return {"status":"BLOCKED","native_http_pairs_verified":0,
                "cause":"strict_correlation_verifier_rejected_evidence"}
    return {
        "status":r["status"],
        "native_http_pairs_verified":r["native_http_pairs_verified"],
        "adapter_completion_observations":r["adapter_completion_observations"],
        "issues":r["issues"],
    }


def run(sha: str) -> dict:
    historical=_check_setup(sha)
    old_umask=os.umask(0o077)
    services=[]
    key=None
    native_exit=None
    timed_out=False
    scoped=None
    setup_failure=None
    try:
        keyfile=PRIVATE/"h2_correlation_key.private.bin"
        with keyfile.open("xb") as out:
            key=secrets.token_bytes(32)
            out.write(key)
        keyfile.chmod(0o600)
        services=_service_start(sha,keyfile)
        native_exit,timed_out=_native(sha,key)
        # The native Agent has exited, but its last outbound request may
        # still be in flight. The Provider must stay alive during the drain.
        # Only the NEW H2 run's terminal slots count toward this criterion;
        # H1 remains irreversibly unknown.
        after=audited_snapshot(PRIVATE/"provider_real_ledger.private.jsonl")
        if after["reserved_new"]:
            scoped=drain_run(PRIVATE/"provider_real_ledger.private.jsonl",
                             run_id=RUN_ID,maximum_seconds=80)
        else:
            scoped=after
        # Private observer/MLX services remain up until the evidence window
        # has closed. No further Agent execution is possible after _native().
        expected_at_least=2
        deadline=time.monotonic()+7
        while (len(_read_jsonl(PRIVATE/"h2_http.private.jsonl")) < expected_at_least
               and time.monotonic() < deadline):
            time.sleep(.15)
    except BaseException as exc:
        setup_failure=type(exc).__name__
    finally:
        for process in reversed(services):
            _stop_group(process)
        os.umask(old_umask)
    try:
        ledger=audited_snapshot(PRIVATE/"provider_real_ledger.private.jsonl")
    except (OSError,CloseoutBlocked,ValueError):
        ledger={"new_run_status":"BLOCKED_LEDGER_INTEGRITY",
                "overall_phase_8_3a_integrity":"BLOCKED"}
    try:
        native=_read_json(PRIVATE/"runs"/RUN_ID/"verified_summary.private.json")
    except (OSError,H2Blocked,ValueError):
        native={}
    file_proof=_native_oracle()
    http=_read_jsonl(PRIVATE/"h2_http.private.jsonl")
    native_join=_native_http_correlate(key,http) if key and http else {
        "status":"NOT_ESTABLISHED","native_http_pairs_verified":0}
    backend=[r.get("backend") for r in http]
    codes=[r.get("http_status") for r in http]
    response_ids=[r.get("response_matches_request_id") for r in http]
    # The criterion is stronger than just seeing two HTTP 200 responses.
    # We require LOCAL MLX, the same two native tool/turn events, and
    # independent original bytes. We do NOT confer overall Phase 8.3A PASS.
    h2_scoped_pass=bool(
        setup_failure is None and native_exit == 0 and not timed_out
        and native.get("code_sha")==sha and native.get("mode")=="shadow"
        and native.get("platform")=="hermes"
        and native.get("scenario")=="read_nonce"
        and native.get("input_unchanged") is True
        and native.get("read_proof",{}).get("final_answer_matches_nonce") is True
        and file_proof.get("valid") is True
        and ledger.get("new_run_status")=="SCOPE_COMPLETE"
        and ledger.get("unknown_new")==0
        and ledger.get("responded_new")==ledger.get("attempted_new")
        and 1 <= ledger.get("attempted_new",0) <= PER_CASE_MAX
        and len(http)==2
        and all(code==200 for code in codes)
        and all(b=="mlx" for b in backend)
        and all(m is True for m in response_ids)
        and native_join.get("status")=="PASS"
        and native_join.get("native_http_pairs_verified")==2
    )
    summary={
        "schema":"local-system-one/phase8_3-h2-real-provider-v1",
        "run_id":RUN_ID,
        "source_sha":sha,
        "platform":"hermes",
        "mode":"shadow",
        "main_model":"stepfun/step-5-preview",
        "local_decision_model":"Laya Typed Decisions 421M MLX",
        "local_model_revision":MODEL_REVISION,
        "execution_policy":"observation_only_no_active_authority",
        "native_agent_exit_code":native_exit,
        "native_agent_timed_out":timed_out,
        "native_tool_oracle":file_proof,
        "reported_main_model_usage":{
            k:native.get("usage",{}).get(k) for k in
            ("api_calls","input_tokens","output_tokens","completed","failed")
        },
        "provider_physical_ledger":{
            k:ledger.get(k) for k in (
                "reserved_global","reserved_h1","reserved_new",
                "attempted_new","responded_new","unknown_new",
                "finalized_new","new_run_status","historic_h1_unresolved",
                "overall_phase_8_3a_integrity","global_request_limit",
                "per_run_limit","ledger_digest_sha256",
            )
        },
        "shadow_observer":{
            "runtime_http_events":len(http),
            "http_statuses":codes,
            "backends":backend,
            "response_identity_echo_verified":all(v is True for v in response_ids) if http else False,
            "native_adapter_http":native_join,
        },
        "failure_class":setup_failure,
        "h2_scoped_verdict":"PASS_SCOPED" if h2_scoped_pass else "PARTIAL_OR_BLOCKED",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_UNRESOLVED",
        "real_agent_savings":"NOT_MEASURED",
        "stepfun_provider_credit_debit":"UNKNOWN",
        "native_action_changed_by_system_one":False,
        "active_authority":"NOT_AUTHORIZED",
        "no_more_provider_calls_authorized_by_this_run":True,
    }
    reportpath=PRIVATE/"runs/h2_verified.private.json"
    if reportpath.exists() or reportpath.is_symlink():
        raise H2Blocked("refusing H2 evidence overwrite")
    reportpath.write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n",
                          encoding="utf-8")
    reportpath.chmod(0o600)
    # Never include the HMAC key, raw tool/prompt or Session identities.
    return summary


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-sha",required=True)
    parser.add_argument("--execute-real-step-plan",action="store_true")
    args=parser.parse_args()
    if not args.execute_real_step_plan:
        parser.error("H2 Provider run requires explicit existing-plan opt-in")
    try:
        result=run(args.frozen_sha)
        print(json.dumps(result,indent=2,sort_keys=True))
        if result["h2_scoped_verdict"]!="PASS_SCOPED":
            raise SystemExit(3)
    except (H2Blocked,ValueError,OSError,TypeError,subprocess.SubprocessError):
        print(json.dumps({"status":"BLOCKED",
                          "phase8_3a_overall":"BLOCKED",
                          "no_new_provider_request_started_by_error_handler":True}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
