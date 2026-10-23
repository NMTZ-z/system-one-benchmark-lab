#!/usr/bin/env python3
"""Crash recovery for ONLY the exact H4B subprocess process groups.

The owner may call --status to inspect test-only child liveness, or
--stop-verified to terminate a process group ONLY if the live group
leader's PID, UID, PGID and kernel-recorded start time match the
one recorded immediately after THIS harness spawned it.

Do not kill PID reuse, children whose original leader disappeared,
a process owned by another user, production Gateway or a generic
process discovered by port. On uncertainty BLOCK and ask the owner
to inspect manually. No model calls, no token reads/copies.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from phase8_3_h4b_transaction import BACKUP

LEDGER=BACKUP/"owned_process_groups.private.jsonl"
ROLES=frozenset({"mlx","observer","provider","native"})
EXPECTED_MAX=4


class OwnedProcessBlocked(ValueError):
    pass


def _ps_start(pid: int) -> str | None:
    try:
        proc=subprocess.run(
            ["/bin/ps","-p",str(pid),"-o","lstart="],
            capture_output=True,text=True,timeout=4,check=False,
        )
    except (OSError,subprocess.TimeoutExpired):
        return None
    result=proc.stdout.strip()
    return result if proc.returncode==0 and result else None


def _ps_state(pid: int) -> str | None:
    try:
        r=subprocess.run(
            ["/bin/ps","-p",str(pid),"-o","state="],
            capture_output=True,text=True,timeout=4,check=False,
        )
        return r.stdout.strip() if r.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):
        return None


def _ps_uid(pid: int) -> int | None:
    try:
        proc=subprocess.run(
            ["/bin/ps","-p",str(pid),"-o","uid="],
            capture_output=True,text=True,timeout=4,check=False,
        )
        return int(proc.stdout.strip()) if proc.returncode==0 else None
    except (OSError,ValueError,subprocess.TimeoutExpired):
        return None


def _validated_records() -> list[dict]:
    if LEDGER.is_symlink() or not LEDGER.is_file() or LEDGER.stat().st_mode&0o077:
        raise OwnedProcessBlocked("H4B original private process ledger is unavailable")
    values=[json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]
    if not 1<=len(values)<=EXPECTED_MAX:
        raise OwnedProcessBlocked("unexpected owned subprocess ledger count")
    allowed={"role","pid","pgid","uid","lstart"}
    for row in values:
        if (not isinstance(row,dict) or set(row)!=allowed or
                row["role"] not in ROLES or
                type(row["pid"]) is not int or row["pid"]<=1 or
                row["pid"]!=row["pgid"] or
                row["uid"]!=os.getuid() or
                not isinstance(row["lstart"],str) or not row["lstart"]):
            raise OwnedProcessBlocked("untrusted original process provenance")
    if len({x["pid"] for x in values})!=len(values) or len(
        {x["role"] for x in values})!=len(values):
        raise OwnedProcessBlocked("duplicate PID/group or subprocess role")
    return values


def record_spawn(proc: subprocess.Popen, role: str) -> dict:
    if role not in ROLES or proc.pid<=1:
        raise OwnedProcessBlocked("H4B subprocess role/PID is not allowed")
    if os.getpgid(proc.pid)!=proc.pid or _ps_uid(proc.pid)!=os.getuid():
        raise OwnedProcessBlocked("H4B process must be its own session/group leader")
    lstart=_ps_start(proc.pid)
    if lstart is None:
        raise OwnedProcessBlocked("unable to attest to subprocess kernel start time")
    if LEDGER.is_symlink() or not BACKUP.is_dir() or BACKUP.is_symlink():
        raise OwnedProcessBlocked("no durable H4B private recovery directory")
    row={
        "role":role,
        "pid":proc.pid,
        "pgid":os.getpgid(proc.pid),
        "uid":os.getuid(),
        "lstart":lstart,
    }
    mode="a" if LEDGER.exists() else "x"
    if LEDGER.exists():
        _validated_records()
    with LEDGER.open(mode,encoding="utf-8") as f:
        f.write(json.dumps(row,sort_keys=True)+"\n")
        f.flush()
        os.fsync(f.fileno())
    LEDGER.chmod(0o600)
    _validated_records()
    return {"role":role,"recorded_pid":True,"original_process_group_unique":True}


def _live_matches(row: dict) -> bool | None:
    """None means a live PID is INCONSISTENT: never kill it."""
    pid=row["pid"]
    start=_ps_start(pid)
    state=_ps_state(pid)
    if start is None or state is None or state.startswith("Z"):
        return False
    if start!=row["lstart"] or _ps_uid(pid)!=row["uid"]:
        return None
    try:
        return True if os.getpgid(pid)==row["pgid"]==pid else None
    except ProcessLookupError:
        return False
    except OSError:
        return None


def inspect_owned() -> dict:
    values=_validated_records()
    states={}
    for row in values:
        status=_live_matches(row)
        states[row["role"]]=(
            "LIVE_EXACT_OWNER" if status is True
            else "NOT_RUNNING" if status is False
            else "UNCERTAIN_DO_NOT_KILL"
        )
    return {
        "schema":"local-system-one/phase8_3-h4b-owned-pid-recovery-v1",
        "recorded_child_groups":len(values),
        "statuses":states,
        "test_only":True,
        "all_stopped":all(s=="NOT_RUNNING" for s in states.values()),
        "production_processes_discovered_or_touched":False,
        "active_authority":"NOT_AUTHORIZED",
        "real_provider_requests":0,
    }


def stop_verified() -> dict:
    values=_validated_records()
    # Two-phase validation: refuse to signal ANYTHING if one PID has
    # changed identity or if provenance ledger is unexpected.
    states={row["pid"]:_live_matches(row) for row in values}
    if any(v is None for v in states.values()):
        raise OwnedProcessBlocked("uncertain reused PID/process identity; refuse ALL termination")
    for row in reversed(values):
        if states[row["pid"]] is True:
            try:
                os.killpg(row["pgid"],signal.SIGTERM)
            except ProcessLookupError:
                continue
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        alive=[r for r in values if _live_matches(r) is True]
        if not alive:
            break
        time.sleep(.15)
    for row in reversed(values):
        if _live_matches(row) is True:
            os.killpg(row["pgid"],signal.SIGKILL)
    return inspect_owned()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    x=p.add_mutually_exclusive_group(required=True)
    x.add_argument("--status",action="store_true")
    x.add_argument("--stop-verified",action="store_true")
    a=p.parse_args()
    try:
        report=inspect_owned() if a.status else stop_verified()
        print(json.dumps(report,sort_keys=True,indent=2))
        if not report["all_stopped"] and a.stop_verified:
            raise SystemExit(3)
    except (OwnedProcessBlocked,OSError,ValueError,TypeError,KeyError):
        print(json.dumps({
            "status":"BLOCKED_OWNER_REVIEW_REQUIRED",
            "no_unverified_process_signaled":True,
            "real_provider_requests":0,
        }))
        raise SystemExit(3) from None

if __name__=="__main__":
    main()
