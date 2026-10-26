#!/usr/bin/env python3
"""NEW one-shot H4B official in-process Hermes Agent with macOS rollback.

Distinct from prior H4 Gateway admission BLOCK (H4 evidence immutable).
Preconditions: clean prereg Git SHA, test Home OFF and manual StepFun Plan
route PINNED to hard-cap localhost, previous eight physical slots unchanged,
H4B no artifacts, real Seatbelt write/network denial and durable pre-run
test Home SQLite/plugin/config rollback checkpoint.

The Agent child uses the official hermes_cli.oneshot.run_oneshot (real
AIAgent, not an adapter fake). It runs in a Seatbelt read_file-only
single-case allowlist; all writes outside SQLite/plugin state/new
disposable case and all network beyond localhost 18793/18794 are denied.

At most THREE new genuine physical StepFun calls, counted against the
original 24 globally. Failure does NOT rerun. Every outcome, even
failure before native startup, leads to termination of owned child
process groups, private post-run evidence archive, test Home rollback,
OFF-mode verification and no production Gateway touches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

import yaml

from phase8_3_prepare_shared_dependency_home import (
    TEST_HOME, inspect as home_inspect,
    isolated_test_config, set_test_mode,
)
from phase8_3_pin_stepfun_route import inspect as route_inspect
from phase8_3_refresh_test_plugin import audit as source_audit
from phase8_3_real_hermes_h2 import (
    ROOT, PRIVATE, MODEL_PATH, MODEL_REVISION,
    PROVIDER_PORT, RUNTIME_PORT, OBSERVER_PORT,
    PHYSICAL_GLOBAL_MAX, PER_CASE_MAX,
    _git, _private_directory, _check_port_available,
    _spawn, _poll_http, _base_env, _read_jsonl, _read_json,
)
from phase8_3_transport_closeout import (
    H4B, H4C, H4D, H3_ORIGINAL_SHA256, audited_snapshot, drain_run,
    CloseoutBlocked,
)
from phase8_3_h4b_sandbox import (
    build_policy, sandbox_command,
    probe_sandbox_offline, SandboxUnavailable,
)
from phase8_3_h4b_transaction import (
    prepare as prepare_recovery,
    restore as restore_recovery, BACKUP,
)
from phase8_3_h4b_owned_processes import (
    record_spawn, inspect_owned,
)
from phase8_3_h4b_direct_child import (
    HERMES_PYTHON, CASE_ID,
)

RUN_ID=H4B
CASE_DIR=PRIVATE/"runs"/RUN_ID
H4B_TIMEOUT=90
PROVIDER_LEDGER=PRIVATE/"provider_real_ledger.private.jsonl"
EXPECTED_BEFORE="5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb"


def configure_for_case(case_id: str) -> None:
    """Bind only a separate H4C run; do not mutate original H4B on disk.

    Explicitly scopes all disposable paths AND the SQLite recovery
    and owned PID ledger to h4c_recovery, never h4b_recovery.
    """
    global RUN_ID, CASE_DIR, BACKUP, PROVIDER_LEDGER
    if case_id not in {H4C,H4D}:
        raise H4BBlocked("only independent H4C or separately approved H4D is eligible here")
    import phase8_3_h4b_transaction as tx
    import phase8_3_h4b_owned_processes as owned
    tx.bind_case(case_id)
    owned.bind_case(case_id)
    RUN_ID=case_id
    CASE_DIR=PRIVATE/"runs"/case_id
    BACKUP=tx.BACKUP
    if case_id==H4D:
        PROVIDER_LEDGER=(Path.home()/"Projects/system-one-phase8-3/private/phase8_3_native_real"
                         /"provider_real_ledger.private.jsonl")


def _short_case() -> str:
    return RUN_ID.split("_")[0]


def _private_name(suffix: str) -> Path:
    return PRIVATE/f"{_short_case()}_{suffix}"


def _verified_report() -> Path:
    return PRIVATE/"runs"/f"{_short_case()}_verified.private.json"


def _logfile(kind: str) -> Path:
    return PRIVATE/f"logs/{_short_case()}_{kind}.private.log"


def _child_source() -> Path:
    return ROOT/f"scripts/phase8_3_{_short_case()}_direct_child.py"


class H4BBlocked(ValueError):
    """Real H4B pre-run safety or completion gate not met."""


def _must_not_exist(paths: list[Path]) -> None:
    for path in paths:
        if path.exists() or path.is_symlink():
            raise H4BBlocked("original H4B is not a fresh one-shot experiment")


def _verify_h4b_history_in_its_own_scoped_context() -> dict:
    """Read the frozen H4B rollback proof without H4C path confusion.

    No file writes or credentials: transaction/PID modules are scoped
    temporarily to H4B only while the H4B private verifier executes.
    ALL global paths revert to H4C even if verification raises.
    """
    import phase8_3_h4b_transaction as tx
    import phase8_3_h4b_owned_processes as own
    original_case=H4D if RUN_ID==H4D else H4C
    if tx.CASE_ID!=original_case or own.CASE_ID!=original_case:
        raise H4BBlocked("H4C/H4D scoped rollback provenance not initialized")
    tx.bind_case(H4B)
    own.bind_case(H4B)
    try:
        from phase8_3_verify_h4b_seatbelt_block import verify
        return verify()
    finally:
        tx.bind_case(original_case)
        own.bind_case(original_case)


def _preflight(sha: str) -> dict:
    if not isinstance(sha,str) or len(sha)!=40 or (
        sha!=_git("rev-parse","HEAD") or _git("status","--porcelain=v1")
    ):
        raise H4BBlocked("clean frozen H4B source SHA required")
    _private_directory(PRIVATE)
    if RUN_ID==H4D:
        from phase8_2a_provider_cap import UPSTREAM, ALLOWED_MODEL
        if (UPSTREAM!="https://api.stepfun.com/step_plan/v1/chat/completions"
                or ALLOWED_MODEL!="step-5-preview" or PER_CASE_MAX!=3
                or H4B_TIMEOUT!=90):
            raise H4BBlocked("H4D Plan-only hard physical request/time cap was modified")
        archive=PRIVATE/"h4d_hermes_archive"
        from phase8_3_h4d_readiness import validate_fixed_source_and_model
        validate_fixed_source_and_model(archive,MODEL_PATH)
    _private_directory(PRIVATE/"runs")
    _private_directory(PRIVATE/"logs")
    if subprocess.run(["git","check-ignore","-q",
            f"private/phase8_3_native_real/runs/{RUN_ID}"],
            cwd=ROOT,check=False).returncode!=0:
        raise H4BBlocked("sensitive H4B data is not covered by Git ignore")
    if source_audit(apply=False)["new_isolated_plugin_matches_frozen_commit"] is not True:
        raise H4BBlocked("installed isolated plugin differs from frozen source")
    home=home_inspect(official_auth=True)
    if home["mode"]!="off" or home["credential_stage_ready"] is not True:
        raise H4BBlocked("H4B requires OFF configured fresh test-only Home")
    if route_inspect().get("route_status")!="PINNED_PROXY":
        raise H4BBlocked("main provider credential may bypass StepFun budget proxy")
    if yaml.safe_load((TEST_HOME/"config.yaml").read_text())!=isolated_test_config("off"):
        raise H4BBlocked("unexpected test Home policy/title/canary configuration")
    if not (MODEL_PATH/"rl_agent_config.json").is_file() or MODEL_PATH.is_symlink():
        raise H4BBlocked("pinned local Laya/MLX model unavailable")
    if RUN_ID==H4C:
        # A later trial is forbidden while original H4B local rollback is
        # uncertain. Independently verify its actual frozen private incident,
        # including all 4 owned groups stopped, unchanged test SQLite/auth.
        # Both tx and PID provenance modules are explicitly rebound to H4B
        # *only for this read-only audit*, then ALWAYS restored to H4C
        # before any H4C checkpoint, port allocation or Provider service.
        # No historical backup file is copied or written in either scope.
        historic=_verify_h4b_history_in_its_own_scoped_context()
        if (
            historic.get("H4B_scoped_verdict")!="BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION"
            or historic.get("original_test_sqlite_logically_restored") is not True
            or historic.get("owned_child_process_groups_stopped")!=4
            or historic.get("model_provider_physical_attempts")!=0
            or historic.get("isolated_auth_file_metadata_unchanged") is not True
        ):
            raise H4BBlocked("original H4B baseline/rollback not independently verified")
    previous=audited_snapshot(PROVIDER_LEDGER,new_run=RUN_ID)
    if (previous.get("reserved_global")!=8
            or previous.get("reserved_new")!=0
            or previous.get("reserved_original_h4")!=0
            or (RUN_ID in {H4C,H4D} and previous.get("reserved_original_h4b")!=0)
            or previous.get("historic_h1_unresolved")!=1
            or previous.get("ledger_digest_sha256")!=EXPECTED_BEFORE):
        raise H4BBlocked("exact original 24 physical Provider ledger history changed")
    historical=PRIVATE/"provider_h1_h2_h3_frozen.private.jsonl"
    if (historical.is_symlink() or not historical.is_file()
            or hashlib.sha256(historical.read_bytes()).hexdigest()!=EXPECTED_BEFORE):
        raise H4BBlocked("independent historical H1/H2/H3 snapshot no longer matches")
    _must_not_exist([
        BACKUP, CASE_DIR,
        _verified_report(),
        _logfile("runtime"),_logfile("observer"),
        _logfile("provider"),_logfile("agent"),
        _private_name("http.private.jsonl"),
        _private_name("correlation_key.private.bin"),
    ])
    for port in (RUNTIME_PORT,OBSERVER_PORT,PROVIDER_PORT):
        _check_port_available(port)
    # This OS-level probe writes only to newly created ignored files and
    # proves explicit deny rules are actually enforced by macOS, before
    # even attempting the real local MLX Runtime or HTTP budget proxy.
    probe=probe_sandbox_offline(sandbox_root=PRIVATE)
    if (not all(probe.get(name) is True for name in (
            "seatbelt_enforced", "only_private_test_write_allowed",
            "specific_protected_credential_rule_precedence_verified",
            "outside_file_write_blocked"))
            or probe.get("actual_credential_read_or_write") is not False):
        raise H4BBlocked("real macOS Seatbelt write protection unavailable")
    return previous


def _create_private_case() -> dict:
    if CASE_DIR.exists() or CASE_DIR.is_symlink():
        raise H4BBlocked("original single-use test case already exists")
    oldmask=os.umask(0o077)
    try:
        CASE_DIR.mkdir(mode=0o700)
        target=CASE_DIR/(_short_case()+"_absent_"+secrets.token_hex(12)+".txt")
        assert not target.exists() and not target.is_symlink()
        case={
            "scenario":"read_missing","path":str(target),
            "basename_sha256":hashlib.sha256(target.name.encode()).hexdigest(),
            "was_absent_before_agent":True,
        }
        private_manifest=CASE_DIR/f"{_short_case()}_missing_target.private.json"
        with private_manifest.open("x",encoding="utf-8") as f:
            json.dump(case,f,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        private_manifest.chmod(0o600)
        prompt=(
            "隔离的只读失败恢复测试：请仅通过平台原生 read_file 工具"
            f"读取以下绝对路径的文件：{target}。该文件可能不存在，"
            "请仅调用一次 read_file。如果读取失败，请如实报告文件不存在或失败。"
            "严格禁止 shell、网络、浏览器、其他文件操作、改写路径、创建文件、"
            "虚构文件内容或自行重试。"
        )
        prompt_file=CASE_DIR/f"{_short_case()}_prompt.private.txt"
        with prompt_file.open("x",encoding="utf-8") as f:
            f.write(prompt)
            f.flush()
            os.fsync(f.fileno())
        prompt_file.chmod(0o600)
        scratch=CASE_DIR/"tmp"
        scratch.mkdir(mode=0o700)
        if RUN_ID in {H4C,H4D}:
            service_home=CASE_DIR/"service_home"
            service_home.mkdir(mode=0o700)
            (service_home/"cache").mkdir(mode=0o700)
            (service_home/"huggingface").mkdir(mode=0o700)
    finally:
        os.umask(oldmask)
    return {
        "target_exists":False,
        "manifest_private_and_preagent":True,
        "allowed_native_tool":"read_file",
    }


def _stop_owned_group(proc: subprocess.Popen) -> None:
    """Never kill a PID or process-group not created by this subprocess."""
    if proc is None or not isinstance(proc.pid,int) or proc.pid<=0:
        return
    # start_new_session=True makes pid equal to pgid. An exited parent
    # can leave grandchildren in its group; do not assume poll() means
    # descendants are gone. SIGTERM then bounded SIGKILL to this group.
    try:
        os.killpg(proc.pid,signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=4)


def _services(keyfile: Path) -> list[subprocess.Popen]:
    procs=[]
    env=_base_env()
    if RUN_ID in {H4C,H4D}:
        # Ancillary MLX/Observer/Proxy children must not use the owner's
        # HOME caches/config. Their model path is already pinned absolute.
        # Only the actual sandboxed official Hermes native child inherits
        # the user's HOME to locate its fixed test-only HERMES_HOME.
        service_home=CASE_DIR/"service_home"
        for folder in (service_home,CASE_DIR/"tmp"):
            if folder.is_symlink() or not folder.is_dir() or folder.stat().st_mode&0o077:
                raise H4BBlocked("H4C service scratch not private/ready")
        env.update({
            "HOME":str(service_home),
            "TMPDIR":str(CASE_DIR/"tmp"),
            "XDG_CACHE_HOME":str(service_home/"cache"),
            "HF_HOME":str(service_home/"huggingface"),
            "HF_HUB_OFFLINE":"1",
            "PYTHONDONTWRITEBYTECODE":"1",
        })
    py=sys.executable
    try:
        runtime=_spawn([
            py,"-m","local_system_one",
            "--source",str(MODEL_PATH),
            "--host","127.0.0.1","--port",str(RUNTIME_PORT),
        ],_logfile("runtime"),env=env)
        procs.append(runtime)
        record_spawn(runtime,"mlx")
        health=_poll_http(
            f"http://127.0.0.1:{RUNTIME_PORT}/health",runtime,timeout=45)
        if not isinstance(health,dict):
            raise H4BBlocked("MLX runtime health schema invalid")
        observer=_spawn([
            py,str(ROOT/"scripts/phase8_2a_shadow_proxy.py"),
            "--port",str(OBSERVER_PORT),
            "--destination",f"http://127.0.0.1:{RUNTIME_PORT}",
            "--evidence",str(_private_name("http.private.jsonl")),
            "--run-id",RUN_ID,"--private-key-file",str(keyfile),
        ],_logfile("observer"),env=env)
        procs.append(observer)
        record_spawn(observer,"observer")
        import socket
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if observer.poll() is not None:
                raise H4BBlocked("isolated H4B HMAC observer exited before ready")
            with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1",OBSERVER_PORT))==0:break
            time.sleep(.12)
        else:
            raise H4BBlocked("isolated observer failed to start")
        provider=_spawn([
            py,str(ROOT/"scripts/phase8_2a_provider_cap.py"),
            "--port",str(PROVIDER_PORT),
            "--private-ledger",str(PROVIDER_LEDGER),
            "--run",RUN_ID,
            "--total-cap",str(PHYSICAL_GLOBAL_MAX),
            "--per-run-cap",str(PER_CASE_MAX),
            "--execute-real-provider",
        ],_logfile("provider"),env=env)
        procs.append(provider)
        record_spawn(provider,"provider")
        budget=_poll_http(
            f"http://127.0.0.1:{PROVIDER_PORT}/_budget",provider,timeout=8)
        if budget!={"run":RUN_ID,"used_total":8,"used_run":0,
                    "total_cap":24,"per_run_cap":3}:
            raise H4BBlocked("LIVE budget proxy missing 8/24 original slots or strict 3")
        return procs
    except BaseException:
        for proc in reversed(procs):_stop_owned_group(proc)
        raise


def _sandbox_offline_child_guard() -> dict:
    """Run the ACTUAL official Python imports/toolset guard inside Seatbelt.

    Called BEFORE starting the MLX/Provider proxy or any Agent task.
    If macOS's denial policy blocks even the official Hermes import,
    that is a harmless no-Provider failure and the original test Home
    must be rolled back. Never loosen the sandbox to force a PASS.
    """
    import subprocess
    policy=build_policy(home=TEST_HOME,case_dir=CASE_DIR)
    cmd=sandbox_command(
        policy=policy,interpreter=HERMES_PYTHON,
        entry=_child_source(),
        args=["--check-offline"],
    )
    env=_base_env()
    key=_private_name("correlation_key.private.bin")
    if key.is_symlink() or not key.is_file() or key.stat().st_mode & 0o077:
        raise H4BBlocked("private HMAC reference file not safe")
    env.update({
        "HERMES_HOME":str(TEST_HOME),
        "HERMES_DISABLE_LAZY_INSTALLS":"1",
        "LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE":"isolated-shadow-test-v1",
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX":key.read_bytes().hex(),
        "TMPDIR":str(CASE_DIR/"tmp"),
        "PYTHONDONTWRITEBYTECODE":"1",
    })
    try:
        result=subprocess.run(
            cmd,cwd=CASE_DIR,env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,text=True,timeout=22,check=False,
        )
    except (OSError,subprocess.TimeoutExpired):
        raise H4BBlocked("OS sandbox could not boot the official read-only Agent import") from None
    if result.returncode!=0:
        raise H4BBlocked("official Hermes source failed within strict OS sandbox")
    try:
        evidence=json.loads(result.stdout)
    except (ValueError,TypeError):
        raise H4BBlocked("official sandbox returned unverified preflight evidence") from None
    if (not isinstance(evidence,dict)
            or evidence.get("real_Agent_invoked") is not False
            or evidence.get("only_advertised_native_tool")!="read_file"
            or evidence.get("official_hermes_inprocess_engine_imported") is not True
            or evidence.get("official_oneshot_preamble_zero_provider_passed") is not True
            or evidence.get("exact_absent_target_guard_installed") is not True
            or evidence.get("main_provider_requests")!=0):
        raise H4BBlocked("sandbox toolset/Agent import preflight not attested")
    return {"status":"PASS_SAME_SEATBELT_OFFLINE_ONLY",
            "Agent_invoked":False,"Provider_requests":0}


def _native_child() -> tuple[int,bool]:
    from phase8_3_h4b_sandbox import build_policy,sandbox_command
    policy=build_policy(home=TEST_HOME,case_dir=CASE_DIR)
    command=sandbox_command(
        policy=policy,interpreter=HERMES_PYTHON,
        entry=_child_source(),
        args=["--run-native"],
    )
    env=_base_env()
    env.update({
        "HERMES_HOME":str(TEST_HOME),
        "HERMES_DISABLE_LAZY_INSTALLS":"1",
        "LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE":"isolated-shadow-test-v1",
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX":(
            _private_name("correlation_key.private.bin")).read_bytes().hex(),
        "TMPDIR":str(CASE_DIR/"tmp"),
        "PYTHONDONTWRITEBYTECODE":"1",
    })
    # Additional upstream keys/Proxy vars are never inherited via base_env.
    if any(k in env for k in (
        "STEPFUN_API_KEY","STEPFUN_BASE_URL","OPENAI_API_KEY",
        "ANTHROPIC_API_KEY","HTTPS_PROXY","HTTP_PROXY","ALL_PROXY",
    )):
        raise H4BBlocked("unwanted provider credential in bounded native child")
    log=_logfile("agent")
    if log.exists() or log.is_symlink():
        raise H4BBlocked("H4B native Agent already has a log")
    with log.open("x",encoding="utf-8") as f:
        proc=subprocess.Popen(
            command,cwd=CASE_DIR,env=env,stdin=subprocess.DEVNULL,
            stdout=f,stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            record_spawn(proc,"native")
        except BaseException:
            _stop_owned_group(proc)
            raise
        try:
            rc=proc.wait(timeout=H4B_TIMEOUT if RUN_ID==H4D else H4B_TIMEOUT+12)
            timed_out=False
        except subprocess.TimeoutExpired:
            timed_out=True
            rc=124
        finally:
            _stop_owned_group(proc)
    return rc,timed_out


def _safe_provider_snapshot() -> dict:
    try:
        record=audited_snapshot(PROVIDER_LEDGER,new_run=RUN_ID)
        return {
            k:record.get(k) for k in (
                "reserved_global","reserved_h1","reserved_h2","reserved_h3",
                "reserved_original_h4","reserved_new","attempted_new",
                "responded_new","unknown_new","finalized_new",
                "new_run_status","historic_h1_unresolved",
                "overall_phase_8_3a_integrity","ledger_digest_sha256",
            )
        }
    except (CloseoutBlocked,OSError,ValueError):
        return {"new_run_status":"BLOCKED_LEDGER_INTEGRITY"}


def run(frozen_sha: str) -> dict:
    _preflight(frozen_sha)
    # Durable baseline BEFORE switching to Shadow or starting a service.
    checkpoint=prepare_recovery()
    oldmask=os.umask(0o077)
    started=[]
    rc=None
    timed_out=False
    error_class=None
    restore=None
    try:
        _create_private_case()
        keyfile=_private_name("correlation_key.private.bin")
        with keyfile.open("xb") as f:
            f.write(secrets.token_bytes(32))
            f.flush()
            os.fsync(f.fileno())
        keyfile.chmod(0o600)
        shadow=set_test_mode("shadow")
        if shadow["mode"]!="shadow":
            raise H4BBlocked("isolated Hermes test Home would not enter Shadow")
        # This is the same sandbox policy and official code module that the
        # real child will use. A failure cannot consume a StepFun request.
        _sandbox_offline_child_guard()
        started=_services(keyfile)
        provider_deadline=(time.monotonic()+90) if RUN_ID==H4D else None
        rc,timed_out=_native_child()
        state=audited_snapshot(PROVIDER_LEDGER,new_run=RUN_ID)
        if state["reserved_new"]:
            # New H4D physical request accounting is strictly bound by
            # the 90-second single-trial wall-clock cap. Old H4B/C code
            # keeps its own historical logic unchanged.
            remaining=max(0,min(80,provider_deadline-time.monotonic())) if provider_deadline else 80
            state=drain_run(
                PROVIDER_LEDGER,run_id=RUN_ID,maximum_seconds=remaining,
            )
        # Let ONLY already launched local observer callbacks close out.
        until=min(time.monotonic()+7,provider_deadline) if provider_deadline else time.monotonic()+7
        while time.monotonic()<until:
            if len(_read_jsonl(_private_name("http.private.jsonl")))>=3:
                break
            time.sleep(.15)
    except BaseException as exc:
        error_class=type(exc).__name__
    finally:
        for proc in reversed(started):_stop_owned_group(proc)
        # Never restore SQLite/plugin bytes while a process that may still
        # write to them is running. An identity mismatch is a STOP, not a
        # reason to guess which external process to kill.
        process_provenance_ok=False
        provenance_error=None
        try:
            import phase8_3_h4b_owned_processes as owner
            if owner.LEDGER.is_file() and not owner.LEDGER.is_symlink():
                process_provenance_ok=inspect_owned()["all_stopped"] is True
            elif not started:
                # Setup failed before a successfully recorded service;
                # _services terminates all its own created groups on error.
                process_provenance_ok=True
            else:
                provenance_error="OWNED_PROCESS_LEDGER_UNAVAILABLE"
        except BaseException as exc:
            provenance_error=type(exc).__name__
        if process_provenance_ok:
            try:
                restore=restore_recovery()
            except (OSError,ValueError,TypeError) as exc:
                restore={"status":"ROLLBACK_REQUIRES_OWNER_ACTION",
                         "error_class":type(exc).__name__}
        else:
            restore={
                "status":"ROLLBACK_PAUSED_UNTIL_ALL_OWNED_CHILDREN_VERIFIED_STOPPED",
                "error_class":provenance_error or "OWNED_CHILD_STILL_ALIVE",
            }
            error_class=error_class or "OwnedProcessCleanupBlocked"
        os.umask(oldmask)

    report={
        "schema":f"local-system-one/phase8_3-{_short_case()}-gateway-independent-native-v1",
        "run_id":RUN_ID,
        "candidate_source_sha":frozen_sha,
        "main_model":"stepfun/step-5-preview",
        "agent_platform":"official_hermes_inprocess_AIAgent",
        "model_execution_route":"macOS_Seatbelt_to_local_physical_budget_proxy",
        "H4D_real_case_if_any":"approved_step_plan_only_3_physical_90s_no_payg" if RUN_ID==H4D else None,
        "allowed_native_tool":"read_file_exact_absent_target",
        "mode_during_task":"shadow",
        "native_child_exit_code":rc,
        "native_child_timed_out":timed_out,
        "private_original_file_still_missing":(
            not any(CASE_DIR.glob(f"{_short_case()}_absent_*.txt"))
        ) if CASE_DIR.is_dir() else None,
        "physical_provider":_safe_provider_snapshot(),
        "local_rollback":{
            k:restore.get(k) for k in (
                "status","mode","sqlite_logical_snapshot_restored",
                "plugin_private_state_restored",
                "test_config_restored","test_plugin_source_restored",
                "credential_metadata_unchanged",
                "credential_residual_if_any",
                "production_files_touched",
            )
        } if restore else {"status":"NOT_RECORDED"},
        "error_class":error_class,
        "real_native_tool_proof":"PENDING_POSTRUN_INDEPENDENT_ADJUDICATION",
        "real_retry_advisory_proof":"PENDING_POSTRUN_INDEPENDENT_ADJUDICATION",
        f"{_short_case()}_acceptance":"NOT_YET_ADJUDICATED",
        "phase8_3a_global":"BLOCKED_HISTORICAL_H1_UNRESOLVED",
        "model_billing_spend":"UNKNOWN",
        "active_authority":"NOT_AUTHORIZED",
        "retries_or_new_agent_tasks_started_automatically":0,
    }
    evidence=_verified_report()
    if evidence.exists() or evidence.is_symlink():
        raise H4BBlocked("original H4B one-shot report already exists")
    evidence.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",
                        encoding="utf-8")
    evidence.chmod(0o600)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    arg=ap.add_mutually_exclusive_group(required=True)
    arg.add_argument("--check-offline",action="store_true")
    arg.add_argument("--execute-real-step-plan",action="store_true")
    ap.add_argument("--frozen-sha",required=True)
    opts=ap.parse_args()
    try:
        if opts.check_offline:
            prev=_preflight(opts.frozen_sha)
            print(json.dumps({
                "status":f"{_short_case().upper()}_SAFE_TO_PREPARE_ROLLBACK",
                "frozen_sha":opts.frozen_sha,
                "current_physical_requests":prev["reserved_global"],
                "unresolved_h1":prev["historic_h1_unresolved"],
                "native_Agent_not_started":True,
                "stepfun_provider_calls_this_check":0,
                "macos_seatbelt_write_boundary_verified":True,
                "rollback_prepared":False,
                "active_authority":"NOT_AUTHORIZED",
            },sort_keys=True,indent=2))
            return
        result=run(opts.frozen_sha)
        print(json.dumps(result,sort_keys=True,indent=2))
        # An actual native H4B task cannot get a PASS from this orchestration
        # summary alone. That requires the independent POSTRUN native SQLite,
        # structured file failure, actual Laya HTTP, keyed Retry/Completion
        # join and original physical Provider-ledger adjudicator.
        if (result["native_child_exit_code"]!=0 or
                result["local_rollback"].get("status")!="TEST_HOME_STATE_RESTORED"):
            raise SystemExit(3)
    except (H4BBlocked,ValueError,TypeError,OSError,subprocess.SubprocessError):
        print(json.dumps({
            "status":"BLOCKED",
            "active_authority":"NOT_AUTHORIZED",
            "new_provider_request_consumption":"UNKNOWN_IF_ALREADY_STARTED",
        }))
        raise SystemExit(3) from None

if __name__=="__main__":
    main()
