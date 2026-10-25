#!/usr/bin/env python3
"""Mac Seatbelt enforcement for H4B's official in-process Hermes Agent.

Only the *child Agent* is sandbox-exec restricted. It can write inside
the previously isolated Hermes test Home and its ONE brand-new ignored
private case folder, but NOT auth.json or another user's/production
files; it may reach ONLY the two designated local ports 18793/18794.
The budget proxy/service are separately preflighted and terminated
with process groups. No sandbox policy allows external Provider egress.

This module cannot start a model or external network request.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import uuid

from phase8_3_prepare_shared_dependency_home import TEST_HOME
from phase8_3_real_hermes_h2 import PRIVATE

ALLOWED_PORTS=(18793,18794)
SOURCE_ROOT=Path(__file__).resolve().parents[1]
SANDBOX_EXE=Path("/usr/bin/sandbox-exec")


class SandboxUnavailable(ValueError):
    pass


def _safe_scope(path: Path, *, needs_existing: bool) -> Path:
    if path.is_symlink() or '"' in str(path) or "\\" in str(path) or "\n" in str(path):
        raise SandboxUnavailable("sandbox path is symlinked or invalid")
    if needs_existing and (not path.is_dir() or not stat.S_ISDIR(path.stat().st_mode)):
        raise SandboxUnavailable("sandbox scope directory absent")
    return path.absolute()


def build_policy(*, home: Path=TEST_HOME, case_dir: Path,
                 allowed_ports: tuple[int,...]=ALLOWED_PORTS) -> str:
    # H4B is a separate, new private native run. The original H4 data
    # and the shared real Provider ledger are OUTSIDE the child write scope.
    fixed=_safe_scope(home,needs_existing=True)
    if fixed!=TEST_HOME or fixed.parent!=Path.home()/".hermes":
        raise SandboxUnavailable("sandbox can only use original dedicated test Home")
    if (case_dir.name not in {"h4b_missing_read","h4c_missing_read"} or
            case_dir.parent != PRIVATE/"runs" or
            not case_dir.is_dir() or case_dir.is_symlink() or
            case_dir.stat().st_mode & 0o077):
        raise SandboxUnavailable("sandbox only accepts brand new restricted H4B case")
    if tuple(allowed_ports)!=ALLOWED_PORTS:
        raise SandboxUnavailable("sandbox must use fixed known localhost ports")
    if not SANDBOX_EXE.is_file():
        raise SandboxUnavailable("macOS Seatbelt sandbox-exec not present")
    local=_safe_scope(case_dir,needs_existing=True)
    auth=fixed/"auth.json"
    if not auth.is_file() or auth.is_symlink():
        raise SandboxUnavailable("isolated credential file must already exist")
    plugin_data=fixed/"plugin-data"
    if plugin_data.is_symlink() or not plugin_data.is_dir():
        raise SandboxUnavailable("isolated test plugin-data root missing")
    states=list(plugin_data.glob("*/state.json"))
    if (len(states)!=1 or states[0].is_symlink()
            or not states[0].is_file()
            or states[0].parent.is_symlink()
            or states[0].parent.stat().st_mode & 0o077):
        raise SandboxUnavailable("test plugin state directory not uniquely isolated")
    plugin_local=states[0].parent
    # No general write access to TEST_HOME: only the prior SQLite store,
    # its pre-existing locks, one plugin's privacy-safe state directory,
    # and new H4B run folder. In particular auth.json, config.yaml,
    # memories, jobs, default Gateway, main repo and NAS are NOT writable.
    # Even a hallucinated write_file cannot modify arbitrary test files.
    dbfiles=(
        "state.db","state.db-shm","state.db-wal",
        "state.db.quarantine.lock","state.db.fts_rebuild.lock",
        "auth.lock",
    )
    write_rules="\n".join(
        f'(allow file-write* (literal "{fixed/name}"))'
        for name in dbfiles)
    # macOS's dynamic loader does not start even /bin/echo with a pure
    # allowlisted file-read policy. The kernel DOES enforce explicit DENY
    # exceptions after an OS boot-compatible file-read* baseline. Protect
    # every unrelated user-home top-level path, owner production Hermes
    # config/profile directories, other Projects and archived test evidence.
    # Denying required files simply blocks the offline in-sandbox boot;
    # we must NOT relax these rules to force a paid test.
    read_denials=[]
    owner=Path.home()
    if owner.is_symlink() or not owner.is_dir():
        raise SandboxUnavailable("owner data Home cannot be trusted")
    def protect(path: Path) -> None:
        text=str(path)
        if path.is_symlink() or '"' in text or "\\" in text or "\n" in text:
            raise SandboxUnavailable("unsafe protected user path in Seatbelt policy")
        if path.is_dir():
            read_denials.append(f'(deny file-read* (subpath "{text}"))')
        elif path.is_file():
            read_denials.append(f'(deny file-read* (literal "{text}"))')
    for item in owner.iterdir():
        if item.name not in {".hermes",".local","Projects"}:
            protect(item)
    production=owner/".hermes"
    if not production.is_dir() or production.is_symlink():
        raise SandboxUnavailable("expected installed production Hermes root missing")
    for item in production.iterdir():
        if item.name not in {"hermes-agent","system-one-phase83lab","installs"}:
            protect(item)
    projects=owner/"Projects"
    if not projects.is_dir() or projects.is_symlink():
        raise SandboxUnavailable("source Projects directory missing")
    source_root=SOURCE_ROOT
    if source_root.parent.resolve()!=projects.resolve():
        raise SandboxUnavailable("H4B source must come from expected Projects")
    for item in projects.iterdir():
        if item.resolve()!=source_root.resolve():
            protect(item)
    for item in PRIVATE.iterdir():
        if item.name!="runs":
            protect(item)
    for item in (PRIVATE/"runs").iterdir():
        if item.resolve()!=local.resolve():
            protect(item)
    read_rules="\n".join(read_denials)
    p=f"""(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow sysctl-read)
(allow file-read*)
{read_rules}
(allow file-write* (subpath "{local}"))
(allow file-write* (subpath "{plugin_local}"))
{write_rules}
(allow file-write* (literal "/dev/null"))
(deny file-write* (literal "{auth}"))
(allow network-outbound (remote ip "localhost:18793"))
(allow network-outbound (remote ip "localhost:18794"))
"""
    if "network-outbound" in p and "network-outbound)" in p:
        raise SandboxUnavailable("unrestricted network policy not permitted")
    return p


def sandbox_command(*, policy: str, interpreter: Path, entry: Path,
                    args: list[str]) -> list[str]:
    # Official Hermes Python is normally an installation-managed venv
    # symlink into uv's *pinned local Python runtime*. Such a known symlink
    # is not an attacker-provided path; all other interpreter symlinks
    # are forbidden. Keep the original venv path as argv[0] so Python
    # finds its own Hermes virtualenv.
    official=Path.home()/".hermes/hermes-agent/.venv/bin/python"
    if interpreter.is_symlink():
        target=interpreter.resolve()
        owner_uv=(Path.home()/".local/share/uv/python").resolve()
        interpreter_ok=(
            interpreter==official and target.is_file()
            and target.is_relative_to(owner_uv))
    else:
        interpreter_ok=interpreter.is_file()
    if (not policy.startswith("(version 1)\n(deny default)")
            or "allow network-outbound\n" in policy
            or not interpreter_ok
            or not entry.is_file() or entry.is_symlink()):
        raise SandboxUnavailable("invalid native sandbox invocation")
    # sandbox-exec accepts -p source without adding a policy file to a
    # potentially credential-bearing Hermes Home.
    return [str(SANDBOX_EXE),"-p",policy,str(interpreter),str(entry),*args]


def probe_sandbox_offline(*, sandbox_root: Path) -> dict:
    """Disposable synthetic paths test real macOS enforcement, 0 models."""
    # This is NOT the production/test Hermes Home. It can be used on any
    # Mac sandbox-exec host to prove an explicit denied file overrides allow.
    sandbox_root=_safe_scope(sandbox_root,needs_existing=True)
    if sandbox_root.stat().st_mode & 0o077:
        raise SandboxUnavailable("offline probe root must be owner-only")
    temporary=sandbox_root/("seatbelt-probe-"+uuid.uuid4().hex[:10])
    temporary.mkdir(mode=0o700)
    protected=temporary/"protected.test"
    protected.write_text("original-test-only")
    allowed=temporary/"allowed.test"
    outside=Path("/private/tmp")/("phase83-sandbox-outside-"+uuid.uuid4().hex[:10])
    body=f"""(version 1)
(deny default)
(allow process-exec)
(allow process-fork)
(allow sysctl-read)
(allow file-read*)
(allow file-write* (subpath "{temporary}"))
(deny file-write* (literal "{protected}"))
"""
    code=("""
from pathlib import Path
import json,sys
allowed,protected,outside=map(Path,sys.argv[1:])
success={}
for label,path in (("allowed",allowed),("protected",protected),("outside",outside)):
 try:
  path.write_text("probe")
  success[label]=True
 except OSError:
  success[label]=False
print(json.dumps(success))
""")
    try:
        outcome=subprocess.run(
            [str(SANDBOX_EXE),"-p",body,str(Path(sys.executable)),"-c",code,
             str(allowed),str(protected),str(outside)],
            capture_output=True,text=True,timeout=12,check=False,
        )
        import json
        result=json.loads(outcome.stdout) if outcome.returncode==0 else {}
        verified=(
            result=={"allowed":True,"protected":False,"outside":False}
            and protected.read_text()=="original-test-only"
            and not outside.exists()
        )
        if not verified:
            raise SandboxUnavailable("macOS Seatbelt deny/allow probe failed")
        return {
            "seatbelt_enforced":True,
            "only_private_test_write_allowed":True,
            "specific_protected_credential_rule_precedence_verified":True,
            "outside_file_write_blocked":True,
            "actual_credential_read_or_write":False,
            "main_provider_requests":0,
        }
    finally:
        allowed.unlink(missing_ok=True)
        outside.unlink(missing_ok=True)
        protected.unlink(missing_ok=True)
        temporary.rmdir()
