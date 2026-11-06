"""Synthetic exact nonproduction Hermes rollback, no keys/Agent/Provider calls."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sqlite3
import stat

import pytest

ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_h4b_transaction as recovery


@pytest.fixture
def fake_test_home(tmp_path,monkeypatch):
    fakeuser=tmp_path/"home"
    fakeuser.mkdir()
    home=fakeuser/".hermes/system-one-phase83lab"
    home.mkdir(parents=True,mode=0o700)
    private=tmp_path/"private"
    private.mkdir(mode=0o700)
    src=home/"plugins/local-system-one-hermes"
    src.mkdir(parents=True,mode=0o700)
    plugin=src/"__init__.py"
    plugin.write_text("PUBLIC_SYNTHETIC_PLUGIN_ORIGINAL")
    plugin.chmod(0o600)
    stateroot=home/"plugin-data/native_only"
    stateroot.mkdir(parents=True,mode=0o700)
    stateroot.parent.chmod(0o700)
    state=stateroot/"state.json"
    state.write_text('{"events":[1,2]}')
    state.chmod(0o600)
    config=home/"config.yaml"
    # Actual restricted H4B scaffold also starts as OFF.
    from phase8_3_prepare_shared_dependency_home import isolated_test_config
    import yaml
    config.write_text(yaml.safe_dump(isolated_test_config("off"),sort_keys=False))
    config.chmod(0o600)
    credential=home/"auth.json"
    credential.write_text('{"synthetic_fixture_only":true}')
    credential.chmod(0o600)
    db=home/"state.db"
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE native (value TEXT)')
        conn.execute('INSERT INTO native VALUES (?)',('pre-H4B',))
        conn.commit()
    db.chmod(0o600)
    monkeypatch.setattr(Path,"home",classmethod(lambda cls:fakeuser))
    monkeypatch.setattr(recovery,"TEST_HOME",home)
    monkeypatch.setattr(recovery,"PRIVATE",private)
    monkeypatch.setattr(recovery,"DB",db)
    monkeypatch.setattr(recovery,"PLUGIN_ROOT",stateroot.parent)
    monkeypatch.setattr(recovery,"CONFIG",config)
    monkeypatch.setattr(recovery,"PUBLIC_PLUGIN",plugin)
    monkeypatch.setattr(recovery,"AUTH",credential)
    backup=private/"h4b_recovery"
    monkeypatch.setattr(recovery,"BACKUP",backup)
    monkeypatch.setattr(recovery,"MANIFEST",backup/"manifest.private.json")
    monkeypatch.setattr(recovery,"PRE_DB",backup/"state_before.private.db")
    monkeypatch.setattr(recovery,"POST_DB",backup/"state_after.private.db")
    monkeypatch.setattr(recovery,"PRE_STATE",backup/"plugin_before.private.json")
    monkeypatch.setattr(recovery,"PRE_PLUGIN_LOCK",backup/"plugin_lock_before.private.bin")
    monkeypatch.setattr(recovery,"POST_STATE",backup/"plugin_after.private.json")
    monkeypatch.setattr(recovery,"FINAL_REPORT",backup/"rollback_status.private.json")
    monkeypatch.setattr(recovery,"_no_listeners",lambda:None)
    return home,private,plugin,state,config,credential,db


def test_backup_mutate_restore_is_idempotent_and_creds_not_backed_up(fake_test_home):
    home,private,plugin,state,config,credential,db=fake_test_home
    initial_credential=credential.read_bytes()
    before=plugin.read_bytes(),state.read_bytes(),config.read_bytes()
    started=recovery.prepare()
    assert started["status"]=="DURABLE_RECOVERY_READY"
    assert started["credential_contents_accessed"] is False
    assert recovery.inspect()["status"]=="BASELINE_VERIFIED"
    assert recovery.BACKUP.stat().st_mode & 0o077 == 0
    assert "auth" not in " ".join(x.name for x in recovery.BACKUP.iterdir()).lower()
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO native VALUES (?)",("post-H4B",))
    plugin.write_bytes(b"PUBLIC_SYNTHETIC_PLUGIN_AFTER")
    state.write_bytes(b'{"events":[1,2,3]}')
    config.write_text("mode: shadow\n")
    assert recovery.inspect()["original_sqlite_digest_matches_before"] is False
    result=recovery.restore()
    assert result["status"]=="TEST_HOME_STATE_RESTORED"
    assert result["sqlite_logical_snapshot_restored"] is True
    assert result["credential_metadata_unchanged"] is True
    assert result["production_files_touched"] is False
    assert plugin.read_bytes()==before[0]
    assert state.read_bytes()==before[1]
    assert config.read_bytes()==before[2]
    assert credential.read_bytes()==initial_credential
    assert sqlite3.connect(db).execute('SELECT value FROM native').fetchall()==[('pre-H4B',)]
    assert sqlite3.connect(recovery.POST_DB).execute(
        'SELECT value FROM native').fetchall()==[('pre-H4B',),('post-H4B',)]
    assert recovery.restore()==result
    assert recovery.inspect()["original_sqlite_digest_matches_before"] is True


def test_prepare_rejects_unsafe_home_mode_and_overwrites(fake_test_home):
    _,_,_,_,config,_,_=fake_test_home
    config.write_text("model: untrusted\n")
    with pytest.raises(recovery.RollbackBlocked,match="OFF-only"):
        recovery.prepare()
    assert not recovery.BACKUP.exists()


def test_cannot_overwrite_prior_frozen_recovery(fake_test_home):
    recovery.prepare()
    with pytest.raises(recovery.RollbackBlocked,match="already exists"):
        recovery.prepare()


def test_credential_metadata_changed_is_flagged_but_never_copied(fake_test_home):
    _,_,_,_,_,auth,_=fake_test_home
    recovery.prepare()
    auth.write_text('{"synthetic_fixture_only":true,"new":1}')
    result=recovery.restore()
    assert result["credential_metadata_unchanged"] is False
    assert result["credential_residual_if_any"]=="OWNER_ACTION_REQUIRED"
    assert not any("auth" in p.name for p in recovery.BACKUP.iterdir())


def test_recovery_refuses_plugin_state_symlink(fake_test_home):
    home,private,_,state,_,_,_=fake_test_home
    state.unlink()
    state.symlink_to(private/"absent")
    with pytest.raises(recovery.RollbackBlocked,match="isolated test plugin state"):
        recovery.prepare()


def test_restore_while_owned_port_is_busy_refuses_mutation(fake_test_home,monkeypatch):
    recovery.prepare()
    monkeypatch.setattr(recovery,"_no_listeners",lambda:(_ for _ in ()).throw(
        recovery.RollbackBlocked("test port busy")))
    with pytest.raises(recovery.RollbackBlocked,match="port busy"):
        recovery.restore()
    assert not recovery.POST_DB.exists()


def test_backup_original_digest_tampering_rejected(fake_test_home):
    recovery.prepare()
    recovery.PRE_STATE.write_text('{"forged":1}')
    with pytest.raises(recovery.RollbackBlocked,match="backup"):
        recovery.inspect()
    with pytest.raises(recovery.RollbackBlocked):
        recovery.restore()


def test_native_plugin_temporary_file_is_removed_without_touching_originals(fake_test_home):
    """Abandoned atomic-state temp must not remain after rollback."""
    home,private,plugin,state,config,auth,db=fake_test_home
    lock=state.parent/".state.json.lock"
    lock.write_bytes(b"LOCK_INITIAL_STATE")
    lock.chmod(0o600)
    before_files={p.name:p.read_bytes() for p in state.parent.iterdir()}
    recovery.prepare()
    (state.parent/".state.json.temporary").write_text('{"partial":true}')
    state.write_text('{"events":[1,2,3]}')
    lock.write_bytes(b"LOCK_CHANGED")
    restored=recovery.restore()
    assert restored["status"]=="TEST_HOME_STATE_RESTORED"
    assert {p.name:p.read_bytes() for p in state.parent.iterdir()}==before_files
    assert (state.parent/".state.json.temporary").exists() is False


def test_untrusted_plugin_symlink_temp_blocks_rollback_safely(fake_test_home):
    """Do not follow an unexpected temp symlink or alter target."""
    home,private,plugin,state,config,auth,db=fake_test_home
    recovery.prepare()
    original=state.read_bytes()
    dangerous=state.parent/".state.json.untrusted"
    dangerous.symlink_to(private/"outside")
    try:
        with pytest.raises(recovery.RollbackBlocked,match="symlink"):
            recovery.restore()
        assert state.read_bytes()==original
        assert not (private/"outside").exists()
    finally:
        dangerous.unlink()
    assert recovery.restore()["status"]=="TEST_HOME_STATE_RESTORED"


def test_online_sqlite_wal_state_after_new_native_turn_recovers_logically(fake_test_home):
    """Synthetic session WAL turn is archived then rolled back without data loss."""
    home,private,plugin,state,config,auth,db=fake_test_home
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]=="wal"
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, text TEXT)")
        conn.execute("INSERT INTO messages(text) VALUES (?)",("original-thread",))
        conn.commit()
    recovery.prepare()
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO messages(text) VALUES (?)",("H4B-new-thread",))
        conn.commit()
    recovered=recovery.restore()
    assert recovered["sqlite_logical_snapshot_restored"] is True
    with sqlite3.connect(db) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0]=="wal"
        assert conn.execute("SELECT text FROM messages ORDER BY id").fetchall()==[
            ("original-thread",)]
    with sqlite3.connect(recovery.POST_DB) as conn:
        assert conn.execute("SELECT text FROM messages ORDER BY id").fetchall()==[
            ("original-thread",),("H4B-new-thread",)]


def test_H4C_new_recovery_is_separate_and_original_H4B_evidence_immutable(fake_test_home):
    import hashlib
    home,private,plugin,state,config,auth,db=fake_test_home
    recovery.prepare()  # old H4B frozen baseline
    h4b_old=recovery.BACKUP
    old={str(p.relative_to(h4b_old)):hashlib.sha256(p.read_bytes()).hexdigest()
         for p in h4b_old.iterdir() if p.is_file()}
    recovery.bind_case("h4c_missing_read")
    try:
        assert recovery.CASE_ID=="h4c_missing_read"
        assert recovery.BACKUP==private/"h4c_recovery"
        result=recovery.prepare()
        assert result["status"]=="DURABLE_RECOVERY_READY"
        assert (recovery.BACKUP/"manifest.private.json").is_file()
        assert json.loads(recovery.MANIFEST.read_text())["case_id"]=="h4c_missing_read"
        with sqlite3.connect(db) as c:
            c.execute("INSERT INTO native VALUES (?)",("H4C ONLY",))
        state.write_text('{"events":[1,2,3]}')
        restored=recovery.restore()
        assert restored["status"]=="TEST_HOME_STATE_RESTORED"
        assert sqlite3.connect(db).execute(
            "SELECT value FROM native").fetchall()==[("pre-H4B",)]
        assert state.read_text()=='{"events":[1,2]}'
        assert {str(p.relative_to(h4b_old)):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in h4b_old.iterdir() if p.is_file()}==old
        assert recovery.inspect()["original_sqlite_digest_matches_before"]
    finally:
        recovery.bind_case("h4b_missing_read")


def test_H4C_rollback_rejects_wrong_case_or_reusing_H4B_manifest(fake_test_home):
    home,private,plugin,state,config,auth,db=fake_test_home
    recovery.prepare()
    original_snapshot=recovery.MANIFEST.read_bytes()
    recovery.bind_case("h4c_missing_read")
    try:
        with pytest.raises(recovery.RollbackBlocked,match="checkpoint"):
            recovery.inspect()
        recovery.prepare()
        payload=json.loads(recovery.MANIFEST.read_text())
        payload["case_id"]="h4b_missing_read"
        recovery.MANIFEST.write_text(json.dumps(payload))
        with pytest.raises(recovery.RollbackBlocked,match="safe original Home"):
            recovery.inspect()
        assert (private/"h4b_recovery/manifest.private.json").read_bytes()==original_snapshot
    finally:
        recovery.bind_case("h4b_missing_read")
