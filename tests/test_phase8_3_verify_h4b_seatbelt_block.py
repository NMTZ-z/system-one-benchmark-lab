"""H4B failed sandbox admission and reversible restoration, synthetic cases."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_verify_h4b_seatbelt_block as incident


def fixture():
    original={
        "candidate_source_sha":incident.SOURCE,
        "run_id":incident.RUN_ID,
        "native_child_exit_code":1,
        "native_child_timed_out":False,
        "error_class":None,
        "h4b_acceptance":"NOT_YET_ADJUDICATED",
        "private_original_file_still_missing":True,
    }
    receipt={
        "status":"TEST_HOME_STATE_RESTORED",
        "mode":"off",
        "credential_metadata_unchanged":True,
        "sqlite_logical_snapshot_restored":True,
        "plugin_private_state_restored":True,
        "public_plugin_source_restored":True,
        "test_config_restored":True,
        "production_files_touched":False,
    }
    groups={
        "all_stopped":True,
        "recorded_child_groups":4,
        "statuses":{
            "mlx":"NOT_RUNNING","observer":"NOT_RUNNING",
            "provider":"NOT_RUNNING","native":"NOT_RUNNING",
        },
        "production_processes_discovered_or_touched":False,
    }
    budget={
        "ledger_digest_sha256":incident.H3_ORIGINAL_SHA256,
        "reserved_global":8,
        "reserved_new":0,
        "attempted_new":0,
        "reserved_original_h4":0,
        "historic_h1_unresolved":1,
    }
    kwargs={
        "stderr":"Traceback; with open(os.devnull) raised PermissionError: [Errno 1] Operation not permitted: '/dev/null'",
        "native_sessions":0,
        "old_sqlite_digest":"a"*64,
        "restored_sqlite_digest":"a"*64,
        "target_absent":True,
    }
    return original,receipt,groups,budget,kwargs


def score(parts):
    a,b,c,d,e=parts
    return incident.analyze(a,b,c,d,**e)


def test_actual_H4B_block_reports_no_model_or_original_state_loss():
    result=score(deepcopy(fixture()))
    assert result["H4B_scoped_verdict"]=="BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION"
    assert result["native_agent_constructed"] is False
    assert result["model_provider_physical_attempts"]==0
    assert result["shared_stepfun_total_physical_attempts"]==8
    assert result["historical_h1_outcome_unknown"]==1
    assert result["isolated_auth_file_metadata_unchanged"] is True
    assert result["owned_child_process_groups_stopped"]==4
    assert result["original_test_sqlite_logically_restored"] is True
    assert result["original_H4_gateway_case_unchanged"] is True
    assert result["automatic_second_H4B_retry_authorized"] is False
    assert result["active_authority"]=="NOT_AUTHORIZED"


@pytest.mark.parametrize("mutation",[
    "source","native_success","unknown_provider_spend","rollback_missing",
    "test_auth_changed","plugin_not_restored","PID_reused",
    "native_session_started","wrong_budget_sha","provider_reservation",
    "H1_cleared","wrong_error","target_created","sqlite_not_rolled_back",
])
def test_forged_H4B_incident_fails_closed(mutation):
    a,b,c,d,e=deepcopy(fixture())
    if mutation=="source":a["candidate_source_sha"]="0"*40
    elif mutation=="native_success":a["native_child_exit_code"]=0
    elif mutation=="unknown_provider_spend":d["attempted_new"]=1
    elif mutation=="rollback_missing":b["status"]="MISSING"
    elif mutation=="test_auth_changed":b["credential_metadata_unchanged"]=False
    elif mutation=="plugin_not_restored":b["plugin_private_state_restored"]=False
    elif mutation=="PID_reused":c["statuses"]["native"]="UNCERTAIN_DO_NOT_KILL"
    elif mutation=="native_session_started":e["native_sessions"]=1
    elif mutation=="wrong_budget_sha":d["ledger_digest_sha256"]="0"*64
    elif mutation=="provider_reservation":d["reserved_new"]=1
    elif mutation=="H1_cleared":d["historic_h1_unresolved"]=0
    elif mutation=="wrong_error":e["stderr"]="different Agent exception"
    elif mutation=="target_created":e["target_absent"]=False
    elif mutation=="sqlite_not_rolled_back":e["restored_sqlite_digest"]="0"*64
    with pytest.raises(incident.SandboxIncidentBlocked):
        incident.analyze(a,b,c,d,**e)


def test_source_entirely_readonly_no_new_Agent():
    source=Path(incident.__file__).read_text()
    assert "run_oneshot(" not in source
    assert "Popen(" not in source
    assert "subprocess.run(" not in source
    assert "auth.json" not in source or "token" not in source.lower()
