#!/usr/bin/env python3
"""One-shot bounded real StepFun test through the existing audited 8.2A proxy.

ONLY H1: Hermes OFF, isolated native read_file of a disposable hidden nonce.
Requires a clean frozen source and the freshly authenticated, route-pinned
test Home. NEVER reads auth token, launches Agent without 24/3 request cap,
switches to production, expands actions, performs a retry or merges Git.
All raw run evidence stays in ignored private/. Public stdout is allowlisted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.request import urlopen

from phase8_3_prepare_shared_dependency_home import TEST_HOME, inspect
from phase8_3_pin_stepfun_route import inspect as inspect_route

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "private/phase8_3_native_real"
RUN_ID = "h1_read_off"
PROVIDER_PORT = 18794
PHYSICAL_GLOBAL_MAX = 24
PER_CASE_MAX = 3
NATIVE_TIMEOUT = 90


class PilotBlocked(ValueError):
    pass


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, timeout=12,
        stderr=subprocess.DEVNULL,
    ).strip()


def _private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or not path.resolve().is_relative_to(PRIVATE.resolve()):
        raise PilotBlocked("private test directory missing or symlinked")
    if path.stat().st_mode & 0o077:
        raise PilotBlocked("private test directory permissions unsafe")


def no_conflicting_provider() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.75)
        if sock.connect_ex(("127.0.0.1", PROVIDER_PORT)) == 0:
            raise PilotBlocked("provider cap port is already occupied")


def preflight(sha: str) -> None:
    if not isinstance(sha, str) or len(sha) != 40 or sha != _git("rev-parse", "HEAD"):
        raise PilotBlocked("native source must exactly equal pinned clean commit")
    if _git("status", "--porcelain=v1"):
        raise PilotBlocked("native test requires a clean worktree")
    if _git("check-ignore", "private/phase8_3_native_real/runs/h1_read_off") == "":
        raise PilotBlocked("private run data is not Git-ignored")
    if not PRIVATE.is_dir() or PRIVATE.is_symlink():
        raise PilotBlocked("private test root absent or unsafe")
    _private_directory(PRIVATE)
    info = inspect(official_auth=True)
    route = inspect_route()
    if not info["credential_stage_ready"] or route["route_status"] != "PINNED_PROXY":
        raise PilotBlocked("new Home credential or proxy route not ready")
    if info["mode"] != "off":
        raise PilotBlocked("H1 must observe native OFF, never Shadow/Active")
    no_conflicting_provider()
    runs = PRIVATE / "runs"
    if runs.exists():
        _private_directory(runs)
    else:
        runs.mkdir(mode=0o700)
    if (runs / RUN_ID).exists() or (runs / RUN_ID).is_symlink():
        raise PilotBlocked("H1 is single-shot; refuse to overwrite previous evidence")
    logs = PRIVATE / "logs"
    if logs.exists():
        _private_directory(logs)
    else:
        logs.mkdir(mode=0o700)
    ledger = PRIVATE / "provider_real_ledger.private.jsonl"
    if ledger.exists() or ledger.is_symlink() or (
        PRIVATE / "provider_real_ledger.private.jsonl.lock").exists():
        raise PilotBlocked("unreviewed preexisting provider ledger")
    if (logs / "h1_real_proxy.private.log").exists() or (
        logs / "h1_native.private.log").exists():
        raise PilotBlocked("previous H1 logs exist")
    if (TEST_HOME / "auth.json").is_symlink():
        raise PilotBlocked("test auth symlink prohibited")


def _budget() -> dict:
    with urlopen(f"http://127.0.0.1:{PROVIDER_PORT}/_budget", timeout=3) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise PilotBlocked("invalid local budget JSON")
    return result


def _start_proxy(sha: str, ledger: Path, log: Path):
    env = {
        "HOME": str(Path.home()),
        "PATH": os.environ.get("PATH", "/opt/homebrew/bin:/usr/bin:/bin"),
        "LANG": "en_US.UTF-8",
        "NO_PROXY": "127.0.0.1,localhost",
    }
    cmd = [
        sys.executable, str(ROOT / "scripts/phase8_2a_provider_cap.py"),
        "--port", str(PROVIDER_PORT),
        "--private-ledger", str(ledger),
        "--run", RUN_ID,
        "--total-cap", str(PHYSICAL_GLOBAL_MAX),
        "--per-run-cap", str(PER_CASE_MAX),
        "--execute-real-provider",
    ]
    file = log.open("x", encoding="utf-8")
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=env, stdout=file, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    file.close()
    deadline = time.monotonic() + 8
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise PilotBlocked("budget proxy exited before admission")
            try:
                b = _budget()
            except (OSError, ValueError):
                time.sleep(.15)
                continue
            if (b.get("run") == RUN_ID and b.get("total_cap") == PHYSICAL_GLOBAL_MAX
                    and b.get("per_run_cap") == PER_CASE_MAX
                    and b.get("used_total") == 0 and b.get("used_run") == 0):
                return proc
            raise PilotBlocked("wrong provider proxy identity or budget")
        raise PilotBlocked("budget proxy failed ready check")
    except BaseException:
        _stop_group(proc)
        raise


def _stop_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=4)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=4)


def _run_native(sha: str, log: Path) -> tuple[int, bool]:
    command = [
        sys.executable, str(ROOT / "scripts/phase8_2a_native_run.py"),
        "--platform", "hermes", "--mode", "off",
        "--scenario", "read_nonce",
        "--run", RUN_ID,
        "--expected-sha", sha,
        "--private-root", str(PRIVATE),
        "--hermes-home", str(TEST_HOME),
        "--shadow-log", str(PRIVATE / "collector_events.private.jsonl"),
        "--provider-proxy-port", str(PROVIDER_PORT),
        "--timeout", str(NATIVE_TIMEOUT),
        "--authorize-existing-step-plan",
    ]
    with log.open("x", encoding="utf-8") as output:
        proc = subprocess.Popen(
            command, cwd=ROOT, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return proc.wait(timeout=NATIVE_TIMEOUT + 18), False
        except subprocess.TimeoutExpired:
            _stop_group(proc)
            return proc.returncode or 124, True


def _ledger_report(ledger: Path) -> dict:
    if not ledger.is_file():
        return {"present": False, "reserved": 0, "attempted": 0, "responded": 0,
                "outcome_unknown": 0, "terminal": 0, "status_codes": []}
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x]
    count = Counter(row.get("kind") for row in rows)
    owners = {r.get("run") for r in rows}
    reserved = [row["slot"] for row in rows if row.get("kind") == "reserved"]
    if owners != {RUN_ID} or not 0 <= len(reserved) <= PER_CASE_MAX or (
        len(set(reserved)) != len(reserved)
    ) or len(reserved) > PHYSICAL_GLOBAL_MAX:
        raise PilotBlocked("budget ledger run identity, slots or cap inconsistent")
    return {
        "present": True,
        "reserved": count["reserved"], "attempted": count["attempted"],
        "responded": count["responded"],
        "outcome_unknown": count["outcome_unknown"],
        "terminal": count["result"],
        "status_codes": [row.get("http_status") for row in rows if row.get("kind") == "responded"],
    }


def _drain_completed_provider_responses(
    ledger: Path, *, maximum_seconds: float = 80.0
) -> bool:
    """Wait ONLY for already-reserved local proxy lifecycle to finish.

    Does not initiate any new Provider request. The existing upstream
    transport timeout is 75 seconds; a bounded drain leaves that chance
    to emit a real response or an outcome_unknown before proxy shutdown.
    """
    if not 0 <= maximum_seconds <= 85:
        raise PilotBlocked("invalid bounded Provider lifecycle drain")
    end = time.monotonic() + maximum_seconds
    while True:
        if ledger.is_file():
            rows = [json.loads(line) for line in
                    ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            reserve = {r["slot"] for r in rows if r.get("kind") == "reserved"}
            attempted = {r["slot"] for r in rows if r.get("kind") == "attempted"}
            final = {r["slot"] for r in rows if r.get("kind") == "result"}
            terminal = {r["slot"] for r in rows if r.get("kind") in {
                "responded", "outcome_unknown",
            }}
            if (reserve and reserve == attempted == final == terminal
                    and len(reserve) <= PER_CASE_MAX
                    and len(reserve) == sum(r.get("kind") == "reserved" for r in rows)
                    and {r.get("run") for r in rows} == {RUN_ID}):
                return True
        if time.monotonic() >= end:
            return False
        time.sleep(min(.35, max(.01, end-time.monotonic())))


def _independent_native_proof() -> dict:
    """Reuse prior independently checked Hermes SQLite native identity oracle.

    Never export original file bytes or any native Session/Tool identifier.
    """
    directory = PRIVATE / "runs" / RUN_ID
    db = TEST_HOME / "state.db"
    source = directory / "input.txt"
    if not db.is_file() or not source.is_file():
        return {"valid": False, "reason": "native_sqlite_or_independent_file_missing"}
    from phase8_2a_hermes_paired_verify import _native_sqlite_evidence
    try:
        nonce = source.read_bytes().decode("utf-8")
        uri = f"file:{db.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=3) as conn:
            proof = _native_sqlite_evidence(conn, directory, nonce)
        return {
            "valid": all(proof.values()),
            "native_read_result_paired": proof.get("native_tool_call_result_id_paired") is True,
            "original_file_matches_native_tool": proof.get("native_tool_result_matches_original_file") is True,
            "agent_final_matches_original_file": proof.get("agent_final_matches_original_file") is True,
            "native_provider_route_confirmed": proof.get("original_provider_route_verified") is True,
        }
    except (ValueError, sqlite3.Error, OSError, KeyError, TypeError):
        return {"valid": False, "reason": "independent_native_hermes_sqlite_oracle_failed"}


def run(sha: str) -> dict:
    preflight(sha)
    os.umask(0o077)
    logpath = PRIVATE / "logs"
    ledger = PRIVATE / "provider_real_ledger.private.jsonl"
    proxy = None
    native_status = None
    native_timed_out = False
    failure = None
    drain_complete = False
    try:
        proxy = _start_proxy(sha, ledger, logpath / "h1_real_proxy.private.log")
        native_status, native_timed_out = _run_native(
            sha, logpath / "h1_native.private.log"
        )
        # Do not kill the live HTTP proxy immediately when the native
        # Agent finishes. Hermes may have left an in-flight physical request
        # unrelated to its logical main-call count. Reserve it permanently,
        # allow bounded terminal accounting, never label it free/auxiliary.
        drain_complete = _drain_completed_provider_responses(ledger)
    except BaseException as exc:
        failure = type(exc).__name__
    finally:
        if proxy is not None:
            _stop_group(proxy)
    try:
        accounting = _ledger_report(ledger)
    except (OSError, ValueError, TypeError, PilotBlocked):
        accounting = {"present": False, "budget_integrity": "BLOCKED"}
    proof = _independent_native_proof()
    verified = (
        failure is None and native_status == 0
        and not native_timed_out and drain_complete
        and accounting.get("present") is True
        and accounting["reserved"] > 0
        and accounting["reserved"] == accounting["attempted"]
        == accounting["terminal"] == accounting["responded"]
        and accounting["outcome_unknown"] == 0
        and proof.get("valid") is True
    )
    result = {
        "schema": "local-system-one/phase8_3-native-stepfun-h1-v1",
        "test": RUN_ID, "source_sha": sha,
        "platform": "hermes", "mode": "off",
        "main_model": "stepfun/step-5-preview",
        "decision_model": "laya-typed-decisions-421m (OFF; no inference)",
        "hard_cap_total": PHYSICAL_GLOBAL_MAX,
        "hard_cap_per_run": PER_CASE_MAX,
        "task_timeout_seconds": NATIVE_TIMEOUT,
        "native_runner_returncode": native_status,
        "native_runner_timed_out": native_timed_out,
        "proxy_lifecycle_drain_completed": drain_complete,
        "transport": accounting,
        "independent_native": proof,
        "failure_class": failure,
        "acceptance": "PASS_SCOPED" if verified else "PARTIAL_OR_BLOCKED",
        "main_provider_spend": "UNKNOWN",
        "active_authority": "NOT_AUTHORIZED",
        "production_modified": False,
    }
    output = PRIVATE / "runs/h1_verified.private.json"
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output.exists():
        raise PilotBlocked("refusing to overwrite earlier H1 summary")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.chmod(0o600)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-sha", required=True)
    parser.add_argument("--execute-real-step-plan", action="store_true")
    a = parser.parse_args()
    if not a.execute_real_step_plan:
        parser.error("H1 real Provider requires explicit opt-in; only previous Plan authorized")
    try:
        summary = run(a.frozen_sha)
        print(json.dumps(summary, indent=2, sort_keys=True))
        if summary["acceptance"] != "PASS_SCOPED":
            raise SystemExit(3)
    except (PilotBlocked, subprocess.SubprocessError, OSError, ValueError, TypeError):
        print(json.dumps({"acceptance":"BLOCKED","main_provider_spend":"UNKNOWN",
                          "active_authority":"NOT_AUTHORIZED"}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
