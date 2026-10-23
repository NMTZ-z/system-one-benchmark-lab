#!/usr/bin/env python3
"""OFFLINE official DSH native SDK initialization, no Provider credential.

Starts only initialize/shutdown against the locally pinned DSH checkout using
fresh ignored HOME/DSH_HOME for each mode. Sends NO task, tool command, or
remote model request. Prints strictly allowlisted diagnostic summaries.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
from typing import Any

from phase8_3_prepare_clean_home import (
    PRIVATE_ROOT, DSH_PATCHES, inspect_dsh, _private_mode, _safe_path,
)

ROOT = Path(__file__).resolve().parents[1]
PIN = "477b4f420553e8a52c2fbccc464d7561b239c443"
UPSTREAM = ROOT.parent / (
    "system-one-benchmark-lab/artifacts/upstream/"
    "deepseek-harness-477b4f420553e8a52c2fbccc464d7561b239c443"
)
CLI = UPSTREAM / "apps/cli/lib/bin.js"
SDK_METHODS = ("initialize", "shutdown")


class SDKPreflightError(RuntimeError):
    """Local SDK bootstrap cannot be verified, never provider-qualified."""


def clean_environment(home: Path, parent: dict[str, str] | None = None) -> dict[str, str]:
    """Never inherit any credentials, API proxy or production configuration."""
    environ = os.environ if parent is None else parent
    return {
        "PATH": environ.get("PATH", "/opt/homebrew/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "DSH_HOME": str(home),
        "DSH_TELEMETRY_MODE": "DISABLED",
        "NO_PROXY": "127.0.0.1,localhost",
        "NO_COLOR": "1",
        "LANG": "en_US.UTF-8",
    }


def rpc(identifier: int, method: str, params: dict) -> str:
    if method not in SDK_METHODS:
        raise SDKPreflightError("only initialization/shutdown RPC is permitted")
    return json.dumps({
        "jsonrpc": "2.0", "id": identifier, "method": method, "params": params,
    }, separators=(",", ":")) + "\n"


def validate_environment() -> None:
    if not inspect_dsh():
        raise SDKPreflightError("isolated DSH patches are absent")
    _private_mode(PRIVATE_ROOT, directory=True)
    _private_mode(DSH_PATCHES, directory=True)
    if not CLI.is_file():
        raise SDKPreflightError("pinned local native DSH checkout is missing")
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=8,
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SDKPreflightError("cannot validate pinned DSH native source") from exc
    if sha != PIN:
        raise SDKPreflightError("DSH upstream version differs from frozen pin")
    plugin = ROOT / "integrations/deepseek-harness/local-system-one-dsh/dist/index.js"
    if not plugin.is_file() or plugin.is_symlink():
        raise SDKPreflightError("DSH plugin build is missing")


def native_sdk_init(mode: str, timeout: int = 20) -> dict[str, Any]:
    if mode not in {"off", "shadow"} or not 4 <= timeout <= 25:
        raise SDKPreflightError("invalid mode or bounded offline timeout")
    validate_environment()
    home = PRIVATE_ROOT / ("dsh_sdk_preflight_" + mode)
    _safe_path(home)
    if home.is_symlink():
        raise SDKPreflightError("refusing symlinked SDK isolated home")
    if home.exists():
        _private_mode(home, directory=True)
    else:
        home.mkdir(mode=0o700)
    patch = DSH_PATCHES / ("dsh_sdk_" + mode + ".yml")
    node = "/opt/homebrew/bin/node"
    if not Path(node).is_file():
        raise SDKPreflightError("pinned local Node executable unavailable")
    proc = subprocess.Popen(
        [node, str(CLI), "--profile", "sdk", "--patch", str(patch)],
        cwd=home, env=clean_environment(home),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True, bufsize=1, start_new_session=True,
    )
    events: queue.Queue[dict] = queue.Queue()
    def read():
        assert proc.stdout is not None
        for raw in proc.stdout:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    events.put(obj)
            except (ValueError, UnicodeDecodeError):
                continue
        events.put({"_end": True})
    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    reports: dict[int, dict] = {}
    timed_out = False
    try:
        assert proc.stdin is not None
        proc.stdin.write(rpc(1, "initialize", {
            "cwd": str(home),
            "provider": "stepfun",
            "model": "step-5-preview",
        }))
        proc.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                obj = events.get(timeout=min(0.5, max(0.05, deadline-time.monotonic())))
            except queue.Empty:
                continue
            if obj.get("id") == 1:
                reports[1] = obj
                break
            if obj.get("_end"):
                break
        if 1 not in reports:
            timed_out = True
        if proc.poll() is None:
            proc.stdin.write(rpc(2, "shutdown", {}))
            proc.stdin.flush()
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                try:
                    obj = events.get(timeout=min(0.5, max(0.05, deadline-time.monotonic())))
                except queue.Empty:
                    continue
                if obj.get("id") == 2:
                    reports[2] = obj
                    break
                if obj.get("_end"):
                    break
    finally:
        try:
            proc.stdin.close() if proc.stdin else None
        except OSError:
            pass
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=4)
    init_ok = isinstance(reports.get(1, {}).get("result"), dict)
    shutdown_ok = isinstance(reports.get(2, {}).get("result"), dict)
    error = reports.get(1, {}).get("error")
    return {
        "mode": mode,
        "native_sdk_initialized": init_ok,
        "sdk_shutdown_acknowledged": shutdown_ok,
        "process_exit_code": proc.returncode,
        "initialization_error_code": (
            error.get("code") if isinstance(error, dict)
            and type(error.get("code")) is int else None
        ),
        "offline_init_timed_out": timed_out,
        "credential_imported": False,
        "model_provider_requests": 0,
        "native_task_requests": 0,
        "e2e_real_provider_validation": "NOT_RUN",
        "active_authority": "NOT_AUTHORIZED",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", action="store_true",
                   help="Start native SDK init/shutdown only; never submit Agent task")
    args = p.parse_args()
    if not args.run:
        p.error("explicit --run required")
    try:
        rows = [native_sdk_init(m) for m in ("off", "shadow")]
        print(json.dumps({
            "schema": "local-system-one/phase8_3-sdk-preflight-v1",
            "results": rows,
            "native_provider_requests": 0,
            "real_agent_e2e": "NOT_RUN",
            "real_provider_calls_authorized_by_smoke": False,
        }, sort_keys=True, indent=2))
        if any(not x["native_sdk_initialized"] or not x["sdk_shutdown_acknowledged"]
               for x in rows):
            raise SystemExit(3)
    except (SDKPreflightError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "reason_class": type(exc).__name__,
            "model_provider_requests": 0,
        }))
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
