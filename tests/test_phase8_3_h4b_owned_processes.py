"""Real OS subprocess-group identity checks, no Agent/model/network."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_h4b_owned_processes as own


@pytest.fixture()
def empty_ledger(tmp_path,monkeypatch):
    base=tmp_path/"recovery"
    base.mkdir(mode=0o700)
    file=base/"owned_process_groups.private.jsonl"
    monkeypatch.setattr(own,"BACKUP",base)
    monkeypatch.setattr(own,"LEDGER",file)
    return file


def test_kill_only_matching_frozen_child_process_group(empty_ledger):
    proc=subprocess.Popen(["/bin/sleep","45"],start_new_session=True,
                          stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    try:
        recorded=own.record_spawn(proc,"native")
        assert recorded["original_process_group_unique"]
        assert empty_ledger.stat().st_mode & 0o077==0
        current=own.inspect_owned()
        assert current["statuses"]["native"]=="LIVE_EXACT_OWNER"
        assert not current["all_stopped"]
        terminated=own.stop_verified()
        proc.wait(timeout=4)
        assert terminated["statuses"]["native"]=="NOT_RUNNING"
        assert terminated["all_stopped"]
        assert own.stop_verified()["all_stopped"] is True
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=4)


def test_refuse_pid_reuse_with_changed_kernel_start_time(empty_ledger):
    proc=subprocess.Popen(["/bin/sleep","45"],start_new_session=True,
                          stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    try:
        own.record_spawn(proc,"native")
        rows=[json.loads(line) for line in empty_ledger.read_text().splitlines()]
        rows[0]["lstart"]="Sat Jan  1 00:00:00 2000"
        empty_ledger.write_text(json.dumps(rows[0])+"\n")
        result=own.inspect_owned()
        assert result["statuses"]["native"]=="UNCERTAIN_DO_NOT_KILL"
        with pytest.raises(own.OwnedProcessBlocked,match="uncertain reused PID"):
            own.stop_verified()
        assert proc.poll() is None
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=4)


def test_undeclared_or_unowned_pid_metadata_blocks_signal(empty_ledger):
    empty_ledger.write_text(json.dumps({
        "role":"production_gateway","pid":200,"pgid":200,
        "uid":os.getuid(),"lstart":"a timestamp"
    })+"\n")
    empty_ledger.chmod(0o600)
    with pytest.raises(own.OwnedProcessBlocked,match="untrusted original process provenance"):
        own.inspect_owned()
    with pytest.raises(own.OwnedProcessBlocked):
        own.stop_verified()


def test_absent_process_ledger_cannot_trigger_fallback_kill_by_port(empty_ledger):
    with pytest.raises(own.OwnedProcessBlocked,match="unavailable"):
        own.stop_verified()
    source=Path(own.__file__).read_text()
    assert "os.killpg(row" in source
    assert "_live_matches" in source
    assert "os.kill(" not in source
    assert "pkill" not in source
    assert "killall" not in source
