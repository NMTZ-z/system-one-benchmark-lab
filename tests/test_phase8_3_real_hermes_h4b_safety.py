"""H4B rollback on orchestration abort + honest one-shot source guards."""
from __future__ import annotations
from pathlib import Path
import json
import os
import subprocess
import sys
import time

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h4b as h4b
from phase8_3_transport_closeout import audited_snapshot


def test_new_h4b_cannot_launch_real_task_without_clean_frozen_source():
    with pytest.raises(h4b.H4BBlocked,match="clean frozen"):
        h4b._preflight("0"*40)


def test_h4b_historic_original_ledger_always_starts_from_eight():
    p=ROOT/"private/phase8_3_native_real/provider_real_ledger.private.jsonl"
    if not p.is_file():
        pytest.skip("Local H1/H2/H3 original private ledger not mounted")
    result=audited_snapshot(p,new_run="h4b_missing_read")
    assert result["reserved_global"]==8
    assert result["reserved_new"]==0
    assert result["reserved_original_h4"]==0
    assert result["historic_h1_unresolved"]==1
    assert result["ledger_digest_sha256"]==h4b.EXPECTED_BEFORE


def test_h4b_owned_process_group_cleanup_only_its_child():
    proc=subprocess.Popen(["/bin/sleep","30"],start_new_session=True,
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        h4b._stop_owned_group(proc)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill();proc.wait(timeout=2)


@pytest.mark.parametrize("failure_step",["case_setup","service_start","agent_native"])
def test_orchestration_aborts_and_restores_without_second_model_request(
    tmp_path,monkeypatch,failure_step
):
    private=tmp_path/"private"
    (private/"runs").mkdir(parents=True)
    monkeypatch.setattr(h4b,"PRIVATE",private)
    monkeypatch.setattr(h4b,"CASE_DIR",private/"runs/h4b_missing_read")
    monkeypatch.setattr(h4b,"_preflight",lambda sha:{"reserved_global":8})
    called=[]
    monkeypatch.setattr(h4b,"prepare_recovery",lambda:called.append("snapshot") or {
        "status":"DURABLE_RECOVERY_READY",
    })
    monkeypatch.setattr(h4b,"restore_recovery",lambda:called.append("restore") or {
        "status":"TEST_HOME_STATE_RESTORED",
        "mode":"off","sqlite_logical_snapshot_restored":True,
        "plugin_private_state_restored":True,
        "test_config_restored":True,
        "public_plugin_source_restored":True,
        "credential_metadata_unchanged":True,
        "production_files_touched":False,
    })
    monkeypatch.setattr(h4b,"_safe_provider_snapshot",lambda:{
        "reserved_global":8,"reserved_new":0,"attempted_new":0,
    })
    # The actual Seatbelt import is tested separately. Failure-step
    # injection must reach the intended synthetic native/service branch.
    monkeypatch.setattr(h4b,"_sandbox_offline_child_guard",lambda:{
        "status":"PASS_SAME_SEATBELT_OFFLINE_ONLY",
        "Agent_invoked":False,"Provider_requests":0,
    })
    monkeypatch.setattr(h4b,"_create_private_case",lambda:(
        (_ for _ in ()).throw(h4b.H4BBlocked("synthetic_fail"))
        if failure_step=="case_setup" else {}))
    monkeypatch.setattr(h4b,"set_test_mode",lambda mode:{"mode":mode})
    monkeypatch.setattr(h4b,"_services",lambda key:(
        (_ for _ in ()).throw(h4b.H4BBlocked("synthetic_service_fail"))
        if failure_step=="service_start" else []))
    monkeypatch.setattr(h4b,"_native_child",lambda:(
        (_ for _ in ()).throw(h4b.H4BBlocked("synthetic_native_fail"))
        if failure_step=="agent_native" else (0,False)))
    # No physical model/Observer servers are actually launched in these
    # fail-closed tests; no H4B artifact from the real user's case.
    assert not (private/"runs/h4b_missing_read").exists()
    result=h4b.run("f"*40)
    assert called==["snapshot","restore"]
    assert result["local_rollback"]["status"]=="TEST_HOME_STATE_RESTORED"
    assert result["error_class"]=="H4BBlocked"
    assert result["h4b_acceptance"]=="NOT_YET_ADJUDICATED"
    assert result["physical_provider"]["reserved_global"]==8
    assert result["retries_or_new_agent_tasks_started_automatically"]==0
    assert result["active_authority"]=="NOT_AUTHORIZED"
    assert (private/"runs/h4b_verified.private.json").is_file()


def test_h4b_real_runner_has_separate_true_native_engine_and_OS_sandbox():
    source=Path(h4b.__file__).read_text()
    assert "sandbox_command(" in source
    assert "build_policy(" in source
    assert "prepare_recovery()" in source
    assert "restore_recovery()" in source
    assert '"--execute-real-provider"' in source
    assert '"--total-cap",str(PHYSICAL_GLOBAL_MAX)' in source
    assert '"--per-run-cap",str(PER_CASE_MAX)' in source
    assert '"--run-native"' in source
    assert '"--execute-real-step-plan"' in source or '--execute-real-step-plan' in source
    assert '"H4B is one-shot; refuse existing attempted evidence"' not in source or (
        "H4B" in source)
    assert '"phase8_3a_global":"BLOCKED_HISTORICAL_H1_UNRESOLVED"' in source
    assert 'return process.wait(timeout=H4B_TIMEOUT)' not in source
