#!/usr/bin/env python3
"""Run and independently verify disposable, zero-network Hermes initialization."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

CASES = ("init", "init_repeat", "empty_stepfun", "request_boundary",
         "bootstrap:exit", "provider:exit", "mcp:error", "constructor:exit",
         "tools:exit", "constructor:crash", "constructor:timeout")
CHILD = Path(__file__).with_name("phase8_3_init_child.py").resolve()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("snapshot refuses links and special files")
        result[str(path.relative_to(root))] = {
            "mode": path.stat().st_mode & 0o777,
            "sha256": digest(path) if path.is_file() else None,
        }
    return result


def quoted(path: Path) -> str:
    value = str(path)
    if any(c in value for c in ('"', "\\", "\n", "\r")):
        raise ValueError("unsafe sandbox path")
    return '"' + value + '"'


def build_policy(*, owner: Path, readable: list[Path], mutable: Path) -> str:
    """Boot-compatible OS reads; deny every unrelated user subtree."""
    allowed = [p.resolve(strict=True) for p in readable] + [mutable.resolve(strict=True)]
    denied = []

    def restrict(path):
        if path in allowed:
            return
        if any(p.is_relative_to(path) for p in allowed):
            if path.is_symlink():
                raise ValueError("symlink in sandbox scope")
            for entry in path.iterdir():
                restrict(entry)
        else:
            denied.append(f"(deny file-read* (subpath {quoted(path)}))")

    restrict(owner.parent)
    # No other user data, removable volume or ambient scratch access.
    for path in (Path("/Volumes"), Path("/private/tmp"), Path("/private/var/folders")):
        if path.exists():
            restrict(path)
    return "\n".join([
        "(version 1)", "(deny default)", "(allow process-exec)",
        "(allow sysctl-read)", "(allow file-read*)", *denied,
        f"(allow file-write* (subpath {quoted(mutable.resolve())}))",
        '(allow file-write* (literal "/dev/null"))', "",
    ])


def identity(pid: int) -> dict | None:
    result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "uid=,pgid=,lstart="],
                            capture_output=True, text=True, timeout=3)
    parts = result.stdout.strip().split(maxsplit=2)
    if result.returncode or len(parts) != 3:
        return None
    return {"pid": pid, "uid": int(parts[0]), "pgid": int(parts[1]), "start": parts[2]}


def group_alive(pgid: int) -> bool:
    result = subprocess.run(["/bin/ps", "-axo", "pgid=,stat="],
                            capture_output=True, text=True, timeout=3, check=True)
    return any(int(p[0]) == pgid and not p[1].startswith("Z")
               for line in result.stdout.splitlines() if len(p := line.split()) == 2)


def stop_owned(proc: subprocess.Popen, owned: dict) -> None:
    if proc.poll() is not None:
        return
    if identity(proc.pid) != owned or owned["uid"] != os.getuid() or owned["pgid"] != proc.pid:
        raise RuntimeError("process identity mismatch; no signal sent")
    os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if identity(proc.pid) != owned:
            raise RuntimeError("process identity changed; refuse kill")
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)


def environment(mutable: Path) -> dict:
    return {
        "PATH": "/usr/bin:/bin", "HOME": str(mutable / "home"),
        "HERMES_HOME": str(mutable / "home/hermes"),
        "TMPDIR": str(mutable / "tmp"), "XDG_CACHE_HOME": str(mutable / "cache"),
        "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
        "HERMES_DISABLE_LAZY_INSTALLS": "1", "HERMES_PM_AUTO_SYNC": "0",
        "OPENAI_BASE_URL": "http://127.0.0.1:1/v1", "OPENAI_API_KEY": "offline-dummy",
        "HERMES_NO_BROWSER": "1",
    }


def verify_case(case_dir: Path) -> dict:
    """Read actual files/SQLite/process state, never trust a child PASS flag."""
    manifest = json.loads((case_dir / "manifest.json").read_text())
    process = json.loads((case_dir / "process.json").read_text())
    mutable = case_dir / "mutable"
    post = case_dir / "post"
    admission_file = post / "admission.json"
    admission = json.loads(admission_file.read_text()) if admission_file.exists() else {}
    events_file = post / "events.jsonl"
    events = [json.loads(x) for x in events_file.read_text().splitlines()] if events_file.exists() else []
    db = post / "home/hermes/state.db"
    sessions = None
    if db.exists():
        # Original child has been reaped; inspect the archived disposable DB.
        with sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='sessions'").fetchone():
                sessions = conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
    boundaries = [e["stage"] for e in events if e["event"] == "boundary_reached"]
    restored = snapshot(mutable) == manifest["baseline"]
    stopped = not group_alive(process["pgid"])
    result = {
        "case": manifest["case"], "isolation_admitted": bool(admission) and all(admission.values()),
        "restored": restored, "owned_group_stopped": stopped,
        "protected_sentinel_unchanged": digest(case_dir / "forbidden") == manifest["sentinel_sha256"],
        "boundaries": boundaries, "native_session_rows": sessions,
        # Trace emits return(None) while unwinding too; only the next real
        # conversation call proves the constructor actually returned.
        "constructor_returned": any(e["stage"] == "turn_entry" and e["event"] == "call" for e in events),
        "stage_exceptions": [e for e in events if e["event"] == "stage_exception"],
        "fault_injected": [e["stage"] for e in events if e["event"] == "fault_injected"],
        "exit_origins": [e for e in events if e["event"] == "exit_origin"],
        "blocked_side_effects": [e["operation"] for e in events if e["event"] == "side_effect_blocked"],
        "process_exit": process["exit"], "timed_out": process["timed_out"],
        "external_provider_requests": 0 if admission.get("network_denied") else None,
        "evidence_kind": "real_native_initialization_offline_only",
    }
    return result


def run_case(root: Path, source: Path, python: Path, case: str, timeout: float = 30) -> dict:
    case_dir = root / case.replace(":", "-")
    case_dir.mkdir(mode=0o700)
    mutable = case_dir / "mutable"
    mutable.mkdir(mode=0o700)
    for suffix in ("home/hermes", "tmp", "cache"):
        (mutable / suffix).mkdir(parents=True, mode=0o700)
    config = {"model": {"default": "diagnostic-model", "provider": "custom",
                        "base_url": "http://127.0.0.1:1/v1", "context_length": 32768},
              "mcp_servers": {}, "memory": {"memory_enabled": False, "user_profile_enabled": False},
              "compression": {"enabled": False}}
    (mutable / "home/hermes/config.yaml").write_text(json.dumps(config))
    (mutable / "home/hermes/.env").write_text("")
    forbidden = case_dir / "forbidden"
    forbidden.write_text("synthetic-protected-baseline")
    manifest = {"case": case, "baseline": snapshot(mutable), "sentinel_sha256": digest(forbidden)}
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    shutil.copytree(mutable, case_dir / "before")
    policy = build_policy(owner=Path.home(), readable=[source, CHILD, python.parent.parent,
                          python.resolve().parent.parent], mutable=mutable)
    (case_dir / "policy.sb").write_text(policy)
    env = environment(mutable)
    if case == "empty_stepfun":
        env.pop("OPENAI_API_KEY")
        env.pop("OPENAI_BASE_URL")
    with (case_dir / "stdio.log").open("xb") as output:
        proc = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", policy, str(python), "-I", "-B",
                                 str(CHILD), str(source), str(mutable), case, str(forbidden)],
                                cwd=mutable / "home", env=env, stdin=subprocess.PIPE,
                                stdout=output, stderr=output, start_new_session=True)
        owned = identity(proc.pid)
        if not owned or owned["pgid"] != proc.pid or owned["uid"] != os.getuid():
            proc.stdin.close()
            proc.wait(timeout=3)
            raise RuntimeError("child ownership unavailable; native entry not admitted")
        (case_dir / "process.json").write_text(json.dumps(owned))
        timed_out = False
        try:
            proc.stdin.write(b"GO\n")
            proc.stdin.close()
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            stop_owned(proc, owned)
        except BaseException:
            stop_owned(proc, owned)
            raise
    if group_alive(proc.pid):
        raise RuntimeError("live group remains; refuse restoration")
    owned.update(exit=proc.returncode, timed_out=timed_out)
    (case_dir / "process.json").write_text(json.dumps(owned, indent=2))
    snapshot(mutable)  # refuse link traversal before archival/restoration
    shutil.copytree(mutable, case_dir / "post")
    shutil.rmtree(mutable)
    shutil.copytree(case_dir / "before", mutable)
    result = verify_case(case_dir)
    (case_dir / "verification.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", choices=CASES, action="append")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_case(args.verify), indent=2))
        return 0
    if sys.platform != "darwin" or not all((args.source, args.python, args.output)):
        parser.error("macOS, source snapshot, official Python and a fresh output path required")
    source = args.source.resolve(strict=True)
    python = args.python.absolute()
    if args.output.exists() or args.output.is_symlink():
        parser.error("experiment output must not already exist")
    args.output.mkdir(mode=0o700)
    root = args.output.resolve()
    # Freeze code before the first child. No source changes during this matrix.
    plan = {"id": uuid.uuid4().hex, "cases": args.case or list(CASES),
            "source_digests": {p: digest(source / p) for p in
                               ("hermes_bootstrap.py", "run_agent.py", "hermes_cli/oneshot.py", "agent/agent_init.py")},
            "runner_sha256": digest(Path(__file__)), "child_sha256": digest(CHILD),
            "provider_requests_authorized": 0}
    (root / "preregistration.json").write_text(json.dumps(plan, indent=2))
    results = []
    for case in plan["cases"]:
        result = run_case(root, source, python, case)
        results.append(result)
        print(json.dumps(result), flush=True)
        if not all(result[k] for k in ("isolation_admitted", "restored", "owned_group_stopped", "protected_sentinel_unchanged")):
            break
    (root / "results.json").write_text(json.dumps(results, indent=2))
    return 0 if len(results) == len(plan["cases"]) and all(r["isolation_admitted"] for r in results) else 3


if __name__ == "__main__":
    raise SystemExit(main())
