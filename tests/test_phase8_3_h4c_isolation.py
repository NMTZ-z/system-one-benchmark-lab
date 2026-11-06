"""H4C isolated new case, source proof, no executable Provider tests."""
from __future__ import annotations
from pathlib import Path
import json
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h4b as shared
import phase8_3_h4b_transaction as transaction
import phase8_3_h4b_owned_processes as owned


def test_new_h4c_config_cannot_reuse_old_h4b_recovery_or_logs():
    existing={
        "run":shared.RUN_ID,
        "dir":shared.CASE_DIR,
        "backup":shared.BACKUP,
        "owned_path":owned.LEDGER,
        "transaction_case":transaction.CASE_ID,
    }
    try:
        shared.configure_for_case("h4c_missing_read")
        assert shared.RUN_ID=="h4c_missing_read"
        assert shared.CASE_DIR==shared.PRIVATE/"runs/h4c_missing_read"
        assert shared.BACKUP==shared.PRIVATE/"h4c_recovery"
        assert transaction.CASE_ID=="h4c_missing_read"
        assert transaction.BACKUP==shared.PRIVATE/"h4c_recovery"
        assert owned.LEDGER==shared.PRIVATE/"h4c_recovery/owned_process_groups.private.jsonl"
        assert shared._private_name("http.private.jsonl")==shared.PRIVATE/"h4c_http.private.jsonl"
        assert shared._private_name("correlation_key.private.bin")==shared.PRIVATE/"h4c_correlation_key.private.bin"
        assert shared._logfile("native")==shared.PRIVATE/"logs/h4c_native.private.log"
        assert shared._verified_report()==shared.PRIVATE/"runs/h4c_verified.private.json"
        assert shared._child_source()==ROOT/"scripts/phase8_3_h4c_direct_child.py"
        with pytest.raises(shared.H4BBlocked,match="independent H4C"):
            shared.configure_for_case("h4b_missing_read")
        for path in (
            transaction.BACKUP,owned.LEDGER,shared.CASE_DIR,
            shared._verified_report(),shared._private_name("http.private.jsonl"),
        ):
            assert "h4b_" not in str(path)
    finally:
        transaction.bind_case("h4b_missing_read")
        owned.bind_case("h4b_missing_read")
        shared.RUN_ID=existing["run"]
        shared.CASE_DIR=existing["dir"]
        shared.BACKUP=existing["backup"]


def test_h4c_wrapper_binds_new_run_before_calling_shared_engine():
    wrapper=(ROOT/"scripts/phase8_3_real_hermes_h4c.py").read_text()
    child=(ROOT/"scripts/phase8_3_h4c_direct_child.py").read_text()
    assert 'configure_for_case("h4c_missing_read")' in wrapper
    assert 'configure_for_case("h4c_missing_read")' in child
    assert "--execute-real-provider" not in wrapper
    assert "phase8_3_h4b_direct_child" in child
    assert "phase8_3_real_hermes_h4b" in wrapper


def test_H4C_native_source_requires_historical_H4B_recovery_before_spend():
    source=(ROOT/"scripts/phase8_3_real_hermes_h4b.py").read_text()
    assert "_verify_h4b_history_in_its_own_scoped_context()" in source
    assert "original H4B baseline/rollback not independently verified" in source
    assert 'previous.get("reserved_original_h4b")!=0' in source
    assert 'previous.get("reserved_global")!=8' in source
    assert 'EXPECTED_BEFORE' in source
    assert 'PER_CASE_MAX' in source


def test_H4C_direct_child_exact_missing_file_only():
    script=(ROOT/"scripts/phase8_3_h4b_direct_child.py").read_text()
    assert '"phase83-h4c-one-read-file-only"' in script
    assert 'TARGET_PREFIX="h4c_absent_"' in script
    assert 'CASE_DIR=PRIVATE/"runs"/case_id' in script
    assert 'args.get("path")!=str(target)' in script
    assert 'read_file' in script
    assert 'run_oneshot(' in script


def test_scoped_historical_H4B_read_does_not_leave_H4C_transaction_switched(monkeypatch):
    import sys
    import types
    import phase8_3_h4b_transaction as tx
    import phase8_3_h4b_owned_processes as own
    previous=(tx.CASE_ID,own.CASE_ID)
    try:
        tx.bind_case("h4c_missing_read")
        own.bind_case("h4c_missing_read")
        def fake_historical_read():
            assert tx.CASE_ID=="h4b_missing_read"
            assert own.CASE_ID=="h4b_missing_read"
            assert tx.BACKUP.name=="h4b_recovery"
            assert own.BACKUP.name=="h4b_recovery"
            return {"H4B_scoped_verdict":"BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION"}
        stub=types.ModuleType("phase8_3_verify_h4b_seatbelt_block")
        stub.verify=fake_historical_read
        monkeypatch.setitem(sys.modules,"phase8_3_verify_h4b_seatbelt_block",stub)
        result=shared._verify_h4b_history_in_its_own_scoped_context()
        assert result["H4B_scoped_verdict"]=="BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION"
        assert tx.CASE_ID==own.CASE_ID=="h4c_missing_read"
        stub.verify=lambda:(_ for _ in ()).throw(ValueError("synthetic history failure"))
        with pytest.raises(ValueError,match="synthetic"):
            shared._verify_h4b_history_in_its_own_scoped_context()
        assert tx.CASE_ID==own.CASE_ID=="h4c_missing_read"
    finally:
        tx.bind_case(previous[0])
        own.bind_case(previous[1])
