#!/usr/bin/env python3
"""Disposable SAME-SOURCE Hermes in-process import under a STRONGER Seatbelt.

Never creates/uses the real H4B case or a recovery checkpoint and never
submits a prompt or Agent task. It proves the current official Hermes
run_oneshot / read_file-only toolset can import in the same restricted
user/home/network environment before any new Provider request. Its
Seatbelt policy is STRICTER than the real H4B policy: it prohibits
ALL network and ALL writes outside the one disposable H4B-like
case folder. Original test Home auth/config/SQLite/plugin bytes are
verified unchanged before/after, and the scratch folder is deleted.

A failing import means H4B real execution is BLOCKED, not a reason to
restart the host Gateway or weaken the production isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys

from phase8_3_h4b_sandbox import build_policy, SANDBOX_EXE
from phase8_3_h4b_transaction import (
    TEST_HOME, DB, PUBLIC_PLUGIN, CONFIG, _db_digest,
)
from phase8_3_real_hermes_h2 import PRIVATE, ROOT
from phase8_3_h4b_direct_child import HERMES_PYTHON

ROLES=("hermes_one_shot_import","read_file_only_runtime_toolset")


class RehearsalBlocked(ValueError):
    pass


def _digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise RehearsalBlocked("isolated test Home original file unavailable")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_path() -> Path:
    states=list((TEST_HOME/"plugin-data").glob("*/state.json"))
    if len(states)!=1 or states[0].is_symlink():
        raise RehearsalBlocked("isolated profile state storage ambiguous")
    return states[0]


def _baseline() -> dict:
    state=_state_path()
    auth=TEST_HOME/"auth.json"
    if not auth.is_file() or auth.is_symlink():
        raise RehearsalBlocked("original auth metadata unavailable")
    stamp=auth.stat()
    return {
        "config_digest":_digest(CONFIG),
        "plugin_source_digest":_digest(PUBLIC_PLUGIN),
        "plugin_state_digest":_digest(state),
        "sqlite_logical_digest":_db_digest(DB),
        "credential_stat_only":(stamp.st_ino,stamp.st_size,stamp.st_mtime_ns),
    }


def run() -> dict:
    base=PRIVATE/("h4b_offline_boot_"+secrets.token_hex(5))
    if base.exists() or base.is_symlink():
        raise RehearsalBlocked("disposable nonproduction rehearsal folder unexpectedly exists")
    baseline=_baseline()
    if not PRIVATE.is_dir() or PRIVATE.is_symlink() or PRIVATE.stat().st_mode & 0o077:
        raise RehearsalBlocked("original isolated research private root unavailable")
    base.mkdir(mode=0o700)
    try:
        runs=base/"runs"
        runs.mkdir(mode=0o700)
        case=runs/"h4b_missing_read"
        case.mkdir(mode=0o700)
        (case/"tmp").mkdir(mode=0o700)
        import phase8_3_h4b_sandbox as sandbox
        prior=sandbox.PRIVATE
        try:
            sandbox.PRIVATE=base
            policy=build_policy(home=TEST_HOME,case_dir=case)
        finally:
            sandbox.PRIVATE=prior
        # A strict subset of the intended real Agent rights:
        # only the disposable case writable, ALL network denied.
        safe_lines=[]
        allowed_write=f'(allow file-write* (subpath "{case}"))'
        for line in policy.splitlines():
            line=line.strip()
            if line.startswith("(allow file-write*") and line!=allowed_write:
                continue
            if line.startswith("(allow network-outbound"):
                continue
            safe_lines.append(line)
        policy="\n".join(safe_lines)+"\n"
        if policy.count("(allow file-write*")!=1 or "(allow network-outbound" in policy:
            raise RehearsalBlocked("offline Seatbelt policy is not strictly narrower")
        source_code=r'''
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.home()/".hermes/hermes-agent"))
from hermes_cli.oneshot import run_oneshot,_validate_explicit_toolsets
from toolsets import create_custom_toolset,resolve_toolset
create_custom_toolset("phase83-h4b-one-read-file-only",
  "H4B offline one native read-only tool",tools=["read_file"])
selected,error=_validate_explicit_toolsets(["phase83-h4b-one-read-file-only"])
v={
 "genuine_Hermes_engine_imported":callable(run_oneshot),
 "only_native_read_file_advertised":resolve_toolset("phase83-h4b-one-read-file-only")==["read_file"],
 "official_toolset_validated":error is None and selected==["phase83-h4b-one-read-file-only"],
 "real_Agent_task_invoked":False,
 "real_provider_requests":0,
}
print(json.dumps(v,sort_keys=True))
if not all(v[k] for k in ("genuine_Hermes_engine_imported","only_native_read_file_advertised","official_toolset_validated")):
 sys.exit(3)
'''
        env={
            "HOME":str(Path.home()),
            "PATH":os.environ.get("PATH","/opt/homebrew/bin:/usr/bin:/bin"),
            "HERMES_HOME":str(TEST_HOME),
            "HERMES_DISABLE_LAZY_INSTALLS":"1",
            "PYTHONDONTWRITEBYTECODE":"1",
            "TMPDIR":str(case/"tmp"),
            "NO_PROXY":"127.0.0.1,localhost",
        }
        native=subprocess.run(
            [str(SANDBOX_EXE),"-p",policy,str(HERMES_PYTHON),
             "-c",source_code],
            cwd=case,env=env,capture_output=True,text=True,timeout=25,
        )
        # stderr can contain private original home filenames, never echo it.
        result={}
        if native.returncode==0:
            try:
                result=json.loads(native.stdout)
            except (ValueError,TypeError):
                result={}
        after=_baseline()
        if after!=baseline:
            raise RehearsalBlocked("offline import altered isolated test Home original state")
        if native.returncode!=0 or not isinstance(result,dict) or (
            result.get("genuine_Hermes_engine_imported") is not True
            or result.get("only_native_read_file_advertised") is not True
            or result.get("official_toolset_validated") is not True
            or result.get("real_Agent_task_invoked") is not False
            or result.get("real_provider_requests")!=0
        ):
            raise RehearsalBlocked("official Hermes in-process engine import failed under strict Seatbelt")
        return {
            "status":"PASS_OFFLINE_ENGINE_IMPORT",
            "macos_seatbelt":"ENFORCED",
            "all_network_denied":True,
            "only_disposable_rehearsal_writable":True,
            "test_home_sqlite_config_plugin_unchanged":True,
            "auth_stat_only_unchanged":True,
            "real_Agent_task_run":False,
            "real_StepFun_requests":0,
            "production_gateway_touched":False,
            "original_H4B_case_created":False,
            "active_authority":"NOT_AUTHORIZED",
        }
    finally:
        # Explicitly only the unique folder created by THIS offline probe.
        if base.is_dir() and not base.is_symlink() and base.parent==PRIVATE:
            shutil.rmtree(base)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-offline",action="store_true")
    args=p.parse_args()
    if not args.run_offline:
        p.error("H4B offline import rehearsal only; no real Agent/Provider mode")
    try:
        print(json.dumps(run(),sort_keys=True,indent=2))
    except (RehearsalBlocked,OSError,ValueError,TypeError,
            subprocess.SubprocessError):
        print(json.dumps({
            "status":"BLOCKED",
            "real_provider_requests":0,
            "production_changes":False,
        }))
        raise SystemExit(3) from None

if __name__=="__main__":
    main()
