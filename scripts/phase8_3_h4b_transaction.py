#!/usr/bin/env python3
"""Reversible H4B isolated Hermes test-Home transaction (NO Provider calls).

Safety contract:
- Only the fixed, preexisting standalone test Home; never production.
- SQLite online backups and ONE test plugin state, test config, and
  public plugin bytes. No auth.json/.env or token value ever opened,
  cloned, backed up, modified or placed in Git.
- Native one-shot child will run under macOS Seatbelt: it can only write
  to allowlisted test state files and its new private case.
- Strict OWNER-only ignored snapshot allows later rollback even after
  orchestration crashes. The original H1/H2/H3/H4 test evidence remains
  separate, immutable and never deleted by rollback.
- Rollback only when all isolated test ports are unused. Post-run SQLite
  and plugin metadata evidence is archived BEFORE restoring baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import socket
import tempfile
import time
from typing import Any

from phase8_3_prepare_shared_dependency_home import (
    TEST_HOME, isolated_test_config,
)
from phase8_3_real_hermes_h2 import PRIVATE

H4B_CASE="h4b_missing_read"
H4C_CASE="h4c_missing_read"
H4D_CASE="h4d_missing_read"
CASE_ID=H4B_CASE
BACKUP=PRIVATE/"h4b_recovery"
DB=TEST_HOME/"state.db"
PLUGIN_ROOT=TEST_HOME/"plugin-data"
CONFIG=TEST_HOME/"config.yaml"
PUBLIC_PLUGIN=TEST_HOME/"plugins/local-system-one-hermes/__init__.py"
AUTH=TEST_HOME/"auth.json"
FINGERPRINT_FILES={
    "test_config":CONFIG,
    "test_plugin":PUBLIC_PLUGIN,
}
MANIFEST=BACKUP/"manifest.private.json"
PRE_DB=BACKUP/"state_before.private.db"
POST_DB=BACKUP/"state_after.private.db"
PRE_STATE=BACKUP/"plugin_before.private.json"
POST_STATE=BACKUP/"plugin_after.private.json"
PRE_PLUGIN_LOCK=BACKUP/"plugin_lock_before.private.bin"
FINAL_REPORT=BACKUP/"rollback_status.private.json"
PORTS=(18782,18793,18794)


class RollbackBlocked(ValueError):
    """A test-only reversible state cannot be safely snapshotted/restored."""


def bind_case(case_id: str) -> None:
    """Select a distinct, *case-scoped* snapshot without moving user data.

    The module defaults to the frozen H4B path for backward compatibility.
    H4C must explicitly select its own brand-new recovery directory in a
    separate Python process. No previous H4B recovery can be overwritten.
    """
    global CASE_ID, BACKUP, MANIFEST, PRE_DB, POST_DB
    global PRE_STATE, POST_STATE, PRE_PLUGIN_LOCK, FINAL_REPORT
    if case_id not in {H4B_CASE,H4C_CASE,H4D_CASE}:
        raise RollbackBlocked("unapproved rollback case")
    CASE_ID=case_id
    BACKUP=PRIVATE/({H4B_CASE:"h4b_recovery",H4C_CASE:"h4c_recovery",H4D_CASE:"h4d_recovery"}[case_id])
    MANIFEST=BACKUP/"manifest.private.json"
    PRE_DB=BACKUP/"state_before.private.db"
    POST_DB=BACKUP/"state_after.private.db"
    PRE_STATE=BACKUP/"plugin_before.private.json"
    POST_STATE=BACKUP/"plugin_after.private.json"
    PRE_PLUGIN_LOCK=BACKUP/"plugin_lock_before.private.bin"
    FINAL_REPORT=BACKUP/"rollback_status.private.json"


def _private(path: Path, *, directory: bool) -> None:
    if path.is_symlink():
        raise RollbackBlocked("isolated recovery path may not be a symlink")
    if not path.exists():
        raise RollbackBlocked("isolated recovery path missing")
    mode=path.stat().st_mode
    if directory and not stat.S_ISDIR(mode):
        raise RollbackBlocked("expected owner-only directory")
    if not directory and not stat.S_ISREG(mode):
        raise RollbackBlocked("expected regular private file")
    if mode & 0o077:
        raise RollbackBlocked("recovery path must be owner-only")


def _home_scope(*, allow_test_transients: bool=False) -> Path:
    if TEST_HOME!=Path.home()/".hermes/system-one-phase83lab" or TEST_HOME.is_symlink():
        raise RollbackBlocked("only fixed nonproduction Hermes test Home can be recovered")
    _private(TEST_HOME,directory=True)
    _private(PRIVATE,directory=True)
    _private(PLUGIN_ROOT,directory=True)
    if CONFIG.is_symlink() or not CONFIG.is_file() or PUBLIC_PLUGIN.is_symlink():
        raise RollbackBlocked("unexpected test config/plugin provenance")
    _private(CONFIG,directory=False)
    _private(PUBLIC_PLUGIN,directory=False)
    if AUTH.is_symlink() or not AUTH.is_file():
        raise RollbackBlocked("independent test auth file unavailable")
    _private(AUTH,directory=False)
    _private(DB,directory=False)
    states=list(PLUGIN_ROOT.glob("*/state.json"))
    if (len(states)!=1 or states[0].is_symlink()
            or states[0].parent.is_symlink()):
        raise RollbackBlocked("not exactly one isolated test plugin state")
    _private(states[0],directory=False)
    _private(states[0].parent,directory=True)
    if not allow_test_transients:
        _plugin_inventory(states[0])
    return states[0]


def _plugin_inventory(state: Path) -> dict[str,str]:
    """Record exactly the original test plugin's two known state files.

    No arbitrary plugin-adjacent private data or other profile files may be
    copied. Unknown state storage shape blocks H4B BEFORE the Agent starts.
    """
    local=state.parent
    allowed={"state.json",".state.json.lock"}
    items={}
    for path in local.iterdir():
        if (path.is_symlink() or not path.is_file()
                or path.name not in allowed or path.stat().st_mode & 0o077):
            raise RollbackBlocked("unreviewed plugin file before recovery")
        items[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    if "state.json" not in items:
        raise RollbackBlocked("expected one native plugin state file")
    return items


def _no_listeners() -> None:
    for port in PORTS:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
            sock.settimeout(.4)
            if sock.connect_ex(("127.0.0.1",port))==0:
                raise RollbackBlocked("test-only port still listening; refuse unsafe restore")


def _fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _db_backup(source: Path, destination: Path, *, must_not_exist: bool) -> None:
    if source.is_symlink() or destination.is_symlink():
        raise RollbackBlocked("SQLite source/destination symlink not allowed")
    if must_not_exist and destination.exists():
        raise RollbackBlocked("refuse overwriting existing private SQLite evidence")
    if destination.parent!=BACKUP and destination!=DB:
        raise RollbackBlocked("SQLite must stay in isolated test Home or ignored recovery")
    if must_not_exist:
        with destination.open("xb") as empty:
            empty.flush()
        destination.chmod(0o600)
    target=sqlite3.connect(str(destination),timeout=4)
    try:
        source_uri=f"file:{source.resolve().as_posix()}?mode=ro"
        origin=sqlite3.connect(source_uri,uri=True,timeout=4)
        try:
            origin.backup(target,pages=64,sleep=.05)
        finally:
            origin.close()
        if target.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RollbackBlocked("isolated SQLite backup integrity invalid")
    finally:
        target.close()


def _db_digest(path: Path) -> str:
    uri=f"file:{path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri,uri=True,timeout=4) as db:
        digest=hashlib.sha256()
        for line in db.iterdump():
            digest.update(line.encode("utf-8",errors="replace"))
            digest.update(b"\n")
        return digest.hexdigest()


def _write_new(path: Path, data: bytes) -> None:
    if path.is_symlink() or path.exists():
        raise RollbackBlocked("private recovery file already exists")
    with path.open("xb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    path.chmod(0o600)


def _restore_bytes(source: Path, target: Path) -> None:
    _private(source,directory=False)
    _private(target,directory=False)
    # Atomic replace in the original test-Home directory; no production files.
    temp=target.with_name(target.name+".h4b-restore.tmp")
    if temp.exists() or temp.is_symlink():
        raise RollbackBlocked("untrusted stale restore temp file")
    try:
        with temp.open("xb") as output:
            output.write(source.read_bytes())
            output.flush()
            os.fsync(output.fileno())
        temp.chmod(0o600)
        temp.replace(target)
    finally:
        if temp.exists():
            temp.unlink()


def _auth_metadata() -> dict[str,Any]:
    # Credential bytes are NEVER read/copied. Stat-only provenance lets us
    # flag a residual change that would require owner-controlled repair.
    info=AUTH.stat()
    return {
        "size":info.st_size,
        "modified_ns":info.st_mtime_ns,
        "mode":stat.S_IMODE(info.st_mode),
        "inode":info.st_ino,
    }


def prepare() -> dict[str,Any]:
    state=_home_scope()
    _no_listeners()
    if BACKUP.exists() or BACKUP.is_symlink():
        raise RollbackBlocked("H4B recovery already exists; cannot replace existing baseline")
    # PREPARE requires the current test Home be safely OFF. It will be
    # explicitly switched to Shadow only after the baseline is durable.
    import yaml
    if yaml.safe_load(CONFIG.read_text())!=isolated_test_config("off"):
        raise RollbackBlocked("H4B recovery baseline requires exact OFF-only test config")
    oldmask=os.umask(0o077)
    try:
        BACKUP.mkdir(mode=0o700)
        _write_new(BACKUP/"config_before.private.yml",CONFIG.read_bytes())
        _write_new(BACKUP/"plugin_source_before.private.py",PUBLIC_PLUGIN.read_bytes())
        _write_new(PRE_STATE,state.read_bytes())
        inventory=_plugin_inventory(state)
        original_lock=state.parent/".state.json.lock"
        if original_lock.is_file():
            _write_new(PRE_PLUGIN_LOCK,original_lock.read_bytes())
        _db_backup(DB,PRE_DB,must_not_exist=True)
        manifest={
            "schema":"local-system-one/phase8_3-h4b-test-home-rollback-v1",
            "fixed_home":"~/.hermes/system-one-phase83lab",
            "case_id":CASE_ID,
            "original_test_mode":"off",
            "plugin_state_relative":str(state.relative_to(TEST_HOME)),
            "config_sha256":_fingerprint(CONFIG.read_bytes()),
            "plugin_sha256":_fingerprint(PUBLIC_PLUGIN.read_bytes()),
            "state_sha256":_fingerprint(state.read_bytes()),
            "plugin_preexisting_files_sha256":inventory,
            "sqlite_logical_digest":_db_digest(PRE_DB),
            "original_auth_metadata":_auth_metadata(),
            "old_known_provider_slot_count":8,
            "credentials_copied":False,
            "production_home_backed_up_or_modified":False,
            "prepared_before_native_agent":True,
        }
        _write_new(MANIFEST,(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode())
    finally:
        os.umask(oldmask)
    return {
        "status":"DURABLE_RECOVERY_READY",
        "profile":"fixed_nonproduction_only",
        "protected_test_state_snapshotted":True,
        "sqlite_backup_integrity":"PASS",
        "credential_contents_accessed":False,
        "rollback_entrypoint":"scripts/phase8_3_h4b_transaction.py --restore",
        "main_provider_requests":0,
        "active_authority":"NOT_AUTHORIZED",
    }


def inspect() -> dict[str,Any]:
    state=_home_scope(allow_test_transients=True)
    if BACKUP.is_symlink() or not BACKUP.is_dir():
        raise RollbackBlocked("no durable H4B recovery checkpoint exists")
    _private(BACKUP,directory=True)
    _private(MANIFEST,directory=False)
    report=json.loads(MANIFEST.read_text())
    if (report.get("fixed_home")!="~/.hermes/system-one-phase83lab"
            or report.get("case_id")!=CASE_ID
            or report.get("plugin_state_relative")!=str(state.relative_to(TEST_HOME))
            or report.get("credentials_copied") is not False
            or report.get("original_test_mode")!="off"):
        raise RollbackBlocked("H4B snapshot manifest does not identify safe original Home")
    for stored in (
        BACKUP/"config_before.private.yml",
        BACKUP/"plugin_source_before.private.py",
        PRE_STATE,PRE_DB,
    ):
        _private(stored,directory=False)
    inventory=report.get("plugin_preexisting_files_sha256")
    if (not isinstance(inventory,dict)
            or not set(inventory)<={"state.json",".state.json.lock"}
            or "state.json" not in inventory):
        raise RollbackBlocked("original plugin file inventory missing")
    if ".state.json.lock" in inventory:
        _private(PRE_PLUGIN_LOCK,directory=False)
        if _fingerprint(PRE_PLUGIN_LOCK.read_bytes())!=inventory[".state.json.lock"]:
            raise RollbackBlocked("original private plugin lock content changed")
    if inventory["state.json"]!=report["state_sha256"]:
        raise RollbackBlocked("original native plugin state inventory changed")
    if (_fingerprint((BACKUP/"config_before.private.yml").read_bytes())
            !=report["config_sha256"]
            or _fingerprint((BACKUP/"plugin_source_before.private.py").read_bytes())
            !=report["plugin_sha256"]
            or _fingerprint(PRE_STATE.read_bytes())!=report["state_sha256"]
            or _db_digest(PRE_DB)!=report["sqlite_logical_digest"]):
        raise RollbackBlocked("durable backup does not match original digest")
    return {
        "status":"BASELINE_VERIFIED",
        "baseline_mode":"off",
        "auth_metadata_unchanged":_auth_metadata()==report["original_auth_metadata"],
        "current_profile_state_matches_before":_fingerprint(state.read_bytes())==report["state_sha256"],
        "original_sqlite_digest_matches_before":_db_digest(DB)==report["sqlite_logical_digest"],
        "credentials_copied":False,
        "main_provider_requests":0,
    }


def restore() -> dict[str,Any]:
    state=_home_scope(allow_test_transients=True)
    _no_listeners()
    report=json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    verify=inspect()
    # Refuse malicious/transient symlinks and directories BEFORE touching
    # the original SQLite target, so an unsafe plugin layout cannot lead
    # to a half-restored Home. Only new ordinary files in this dedicated
    # test plugin-data folder are removable.
    known=set(report.get("plugin_preexisting_files_sha256",{}))
    if not known or not known<={"state.json",".state.json.lock"}:
        raise RollbackBlocked("untrusted original plugin file manifest")
    for artifact in state.parent.iterdir():
        if artifact.is_symlink() or not artifact.is_file():
            raise RollbackBlocked("unexpected non-file/symlink plugin artifact")
    # On a pre-run restore, also preserve the exact historical checkpoint;
    # no post-run artifacts are needed until the native process has started.
    prior_exist=POST_DB.exists() or POST_STATE.exists()
    if not prior_exist:
        oldmask=os.umask(0o077)
        try:
            _db_backup(DB,POST_DB,must_not_exist=True)
            _write_new(POST_STATE,state.read_bytes())
        finally:
            os.umask(oldmask)
    else:
        _private(POST_DB,directory=False)
        _private(POST_STATE,directory=False)
    # Restore the original test-only SQLite via official online backup.
    # All real H4B native evidence must be independently verified against
    # POST_DB (the archived state after the Agent), never the reverted DB.
    _db_backup(PRE_DB,DB,must_not_exist=False)
    # The in-process plugin may have created temporary state files before
    # an abrupt failure. Only files in this ONE test-only plugin directory
    # that were not part of the exact original digest inventory are cleaned.
    # Any symlink or directory is blocked to prevent following malicious
    # paths beyond the isolated test Home.
    previously=set(report.get("plugin_preexisting_files_sha256",{}))
    if not previously or not previously<={"state.json",".state.json.lock"}:
        raise RollbackBlocked("untrusted original plugin inventory")
    temporary=[]
    for path in state.parent.iterdir():
        if path.is_symlink() or not path.is_file():
            raise RollbackBlocked("unexpected non-file/symlink plugin artifact")
        if path.name not in previously:
            temporary.append(path)
    for path in temporary:
        path.unlink()
    if ".state.json.lock" in previously:
        original_lock=state.parent/".state.json.lock"
        if not original_lock.is_file() or original_lock.is_symlink():
            raise RollbackBlocked("original native plugin lock disappeared")
        if original_lock.read_bytes()!=PRE_PLUGIN_LOCK.read_bytes():
            _restore_bytes(PRE_PLUGIN_LOCK,original_lock)
    _restore_bytes(PRE_STATE,state)
    _restore_bytes(BACKUP/"config_before.private.yml",CONFIG)
    _restore_bytes(BACKUP/"plugin_source_before.private.py",PUBLIC_PLUGIN)
    final=inspect()
    if (not final["original_sqlite_digest_matches_before"]
            or not final["current_profile_state_matches_before"]
            or _plugin_inventory(state)!=report["plugin_preexisting_files_sha256"]):
        raise RollbackBlocked("H4B full plugin/SQLite state restoration did not verify")
    import yaml
    if yaml.safe_load(CONFIG.read_text())!=isolated_test_config("off"):
        raise RollbackBlocked("test Home not OFF after restoration")
    metadata_unchanged=final["auth_metadata_unchanged"]
    result={
        "status":"TEST_HOME_STATE_RESTORED",
        "mode":"off",
        "sqlite_logical_snapshot_restored":True,
        "plugin_private_state_restored":True,
        "public_plugin_source_restored":True,
        "test_config_restored":True,
        "credentials_backed_up_or_read":False,
        "credential_metadata_unchanged":metadata_unchanged,
        "credential_residual_if_any":"NONE" if metadata_unchanged else "OWNER_ACTION_REQUIRED",
        "postrun_evidence_archived_in_ignored_private":True,
        "production_files_touched":False,
        "active_authority":"NOT_AUTHORIZED",
    }
    if FINAL_REPORT.is_symlink():
        raise RollbackBlocked("existing recovery report is symlinked")
    if FINAL_REPORT.exists():
        _private(FINAL_REPORT,directory=False)
        earlier=json.loads(FINAL_REPORT.read_text(encoding="utf-8"))
        if earlier!=result:
            raise RollbackBlocked("subsequent rollback status differs from original")
    else:
        _write_new(FINAL_REPORT,(json.dumps(result,sort_keys=True,indent=2)+"\n").encode())
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    op=cli.add_mutually_exclusive_group(required=True)
    op.add_argument("--prepare",action="store_true")
    op.add_argument("--check",action="store_true")
    op.add_argument("--restore",action="store_true")
    cli.add_argument("--case",choices=[H4B_CASE,H4C_CASE,H4D_CASE],default=H4B_CASE)
    options=cli.parse_args()
    try:
        bind_case(options.case)
        result=prepare() if options.prepare else restore() if options.restore else inspect()
        print(json.dumps(result,sort_keys=True,indent=2))
    except (RollbackBlocked,ValueError,TypeError,KeyError,OSError,sqlite3.Error):
        print(json.dumps({"status":"BLOCKED",
                          "existing_test_backup_preserved":True,
                          "provider_requests":0,
                          "production_affected":False}))
        raise SystemExit(3) from None

if __name__=="__main__":
    main()
