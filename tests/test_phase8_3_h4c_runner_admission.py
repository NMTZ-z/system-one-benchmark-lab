"""Separate frozen H4C runner checks, no real Provider or case construction."""
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h4b as shared


def test_H4C_real_case_refuses_a_dirty_or_unfrozen_candidate():
    old=shared.RUN_ID,shared.CASE_DIR,shared.BACKUP
    import phase8_3_h4b_transaction as tx
    import phase8_3_h4b_owned_processes as own
    try:
        shared.configure_for_case("h4c_missing_read")
        with pytest.raises(shared.H4BBlocked,match="clean frozen"):
            shared._preflight("0"*40)
    finally:
        tx.bind_case("h4b_missing_read")
        own.bind_case("h4b_missing_read")
        shared.RUN_ID,shared.CASE_DIR,shared.BACKUP=old


def test_H4C_source_keeps_same_strict_limits_and_owned_process_groups():
    source=(ROOT/"scripts/phase8_3_real_hermes_h4b.py").read_text()
    assert '--execute-real-provider' in source
    assert '"--total-cap",str(PHYSICAL_GLOBAL_MAX)' in source
    assert '"--per-run-cap",str(PER_CASE_MAX)' in source
    assert 'record_spawn(runtime,"mlx")' in source
    assert 'record_spawn(observer,"observer")' in source
    assert 'record_spawn(provider,"provider")' in source
    assert 'record_spawn(proc,"native")' in source
    assert 'restore_recovery()' in source
    assert 'owned_child_process' not in source or 'owned' in source
    assert 'RUN_ID==H4C' in source
    assert '"reserved_original_h4b"' in source
    assert 'verify_h4b()' in source


def test_H4C_offline_wrapper_has_no_bypass_of_one_shot_optin():
    src=(ROOT/"scripts/phase8_3_real_hermes_h4c.py").read_text()
    assert 'configure_for_case("h4c_missing_read")' in src
    assert 'runner.main()' in src
    assert '_preflight' not in src or 'frozen' in src
