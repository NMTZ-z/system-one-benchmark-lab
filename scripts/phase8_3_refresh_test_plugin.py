#!/usr/bin/env python3
"""Update ONLY the isolated Hermes test plugin from a clean frozen Git commit.

No production configuration, auth files, network, original SQLite data or
Provider usage is changed. Copy only the public __init__.py file; refuse
other Homes and symlinks and preserve private file permissions. The
previous deployed plugin bytes must equal HEAD's Git parent to prove
that this operation is the intended H4-only change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from phase8_3_prepare_shared_dependency_home import TEST_HOME, PLUGIN_SRC

ROOT=Path(__file__).resolve().parents[1]
SOURCE_REL="integrations/hermes/local-system-one-hermes/__init__.py"
DEST=TEST_HOME/"plugins/local-system-one-hermes/__init__.py"


class TestPluginSyncBlocked(ValueError):
    pass


def _git(*args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git",*args],cwd=ROOT,stderr=subprocess.DEVNULL,timeout=8)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        raise TestPluginSyncBlocked("cannot verify frozen test-only source") from None


def audit(*,apply: bool=False) -> dict:
    if (TEST_HOME != Path.home()/".hermes/system-one-phase83lab"
            or TEST_HOME.is_symlink() or DEST.is_symlink()
            or not TEST_HOME.is_dir() or not DEST.is_file()):
        raise TestPluginSyncBlocked("only the fixed standalone test Home plugin may update")
    if (DEST.stat().st_mode & 0o077)!=0:
        raise TestPluginSyncBlocked("test plugin destination has unsafe permissions")
    status=_git("status","--porcelain").decode().strip()
    if status:
        raise TestPluginSyncBlocked("update requires committed clean candidate")
    candidate=_git("rev-parse","HEAD").decode().strip()
    parent=_git("rev-parse","HEAD^").decode().strip()
    old_source=_git("show",f"{parent}:{SOURCE_REL}")
    new_source=_git("show",f"{candidate}:{SOURCE_REL}")
    if new_source != (PLUGIN_SRC/"__init__.py").read_bytes():
        raise TestPluginSyncBlocked("checked-out public plugin differs from frozen Git")
    dest_bytes=DEST.read_bytes()
    old_digest=hashlib.sha256(old_source).hexdigest()
    new_digest=hashlib.sha256(new_source).hexdigest()
    installed_digest=hashlib.sha256(dest_bytes).hexdigest()
    if installed_digest not in {old_digest,new_digest}:
        raise TestPluginSyncBlocked("unexpected isolated plugin provenance")
    if apply and installed_digest==old_digest and old_digest!=new_digest:
        # Local source only. No secrets. Entire file updated atomically.
        temp=DEST.with_name("__init__.py.h4.tmp")
        if temp.exists() or temp.is_symlink():
            raise TestPluginSyncBlocked("unexpected test source temporary file")
        mask=os.umask(0o077)
        try:
            with temp.open("xb") as fp:
                fp.write(new_source)
                fp.flush()
                os.fsync(fp.fileno())
            temp.chmod(0o600)
            temp.replace(DEST)
        finally:
            os.umask(mask)
        installed_digest=hashlib.sha256(DEST.read_bytes()).hexdigest()
    return {
        "new_isolated_plugin_matches_frozen_commit":installed_digest==new_digest,
        "old_deployed_source_was_exact_parent":installed_digest==old_digest,
        "isolated_test_source_only":True,
        "production_config_changed":False,
        "credential_file_read":False,
        "real_provider_requests":0,
        "source_sha":candidate,
        "active_authority":"NOT_AUTHORIZED",
    }


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    controls=cli.add_mutually_exclusive_group(required=True)
    controls.add_argument("--check",action="store_true")
    controls.add_argument("--apply",action="store_true")
    args=cli.parse_args()
    try:
        outcome=audit(apply=args.apply)
        print(json.dumps(outcome,sort_keys=True,indent=2))
        if args.check and not outcome["new_isolated_plugin_matches_frozen_commit"]:
            raise SystemExit(3)
    except (TestPluginSyncBlocked,OSError,ValueError) as exc:
        print(json.dumps({"status":"BLOCKED",
                          "reason_class":type(exc).__name__,
                          "real_provider_requests":0}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
