"""H4C read-only incident verifier; synthetic original-source tamper fixtures."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_verify_h4c_preactive_block as report


def fixture():
    original={
        "candidate_source_sha":report.ORIGINAL_SHA,
        "run_id":report.RUN_ID,
        "agent_platform":"official_hermes_inprocess_AIAgent",
        "native_child_exit_code":1,
        "native_child_timed_out":False,
        "private_original_file_still_missing":True,
        "h4c_acceptance":"NOT_YET_ADJUDICATED",
    }
    usage={"failure":"SystemExit(1)","failed":True,"api_calls":None}
    receipt={
        "status":"TEST_HOME_STATE_RESTORED",
        "mode":"off","credential_metadata_unchanged":True,
        "sqlite_logical_snapshot_restored":True,
        "plugin_private_state_restored":True,
        "public_plugin_source_restored":True,
        "test_config_restored":True,
        "production_files_touched":False,
    }
    processes={
        "recorded_child_groups":4,
        "all_stopped":True,
        "production_processes_discovered_or_touched":False,
        "statuses":{
            "mlx":"NOT_RUNNING","observer":"NOT_RUNNING",
            "provider":"NOT_RUNNING","native":"NOT_RUNNING",
        },
    }
    budget={
        "reserved_global":8,"reserved_h1":3,
        "reserved_h2":3,"reserved_h3":2,
        "reserved_original_h4":0,
        "reserved_original_h4b":0,
        "reserved_new":0,"attempted_new":0,
        "historic_h1_unresolved":1,
        "ledger_digest_sha256":report.H3_ORIGINAL_SHA256,
    }
    rest={
        "original_sessions":0,"baseline_same":True,
        "target_absent":True,"observer_absent":True,
        "other_H4B_untouched":True,
    }
    return original,usage,receipt,processes,budget,rest


def adjudicate(parts):
    original,usage,receipt,processes,budget,rest=parts
    return report.analyze(original,usage,receipt,processes,budget,**rest)


def test_true_original_H4C_is_blocked_without_suggesting_a_root_cause():
    result=adjudicate(fixture())
    assert result["H4C_outcome"]=="BLOCKED_BEFORE_NATIVE_SESSION_AND_PROVIDER"
    assert result["underlying_initialization_cause"]=="NOT_DETERMINABLE_FROM_ORIGINAL_SUPPRESSED_STDERR"
    assert result["actual_native_session_or_read_file_tool_call"] is False
    assert result["actual_Completion_And_Retry_observations"] is False
    assert result["new_StepFun_physical_requests"]==0
    assert result["global_StepFun_request_count"]==8
    assert result["original_H1_unknown_outcome"]==1
    assert result["local_snapshot_sqlite_restored"] is True
    assert result["test_auth_metadata_unchanged"] is True
    assert result["H4C_owned_process_groups_stopped"]==4
    assert result["original_H4_and_H4B_evidence_unchanged"] is True
    assert result["automatic_H4C_rerun_authorized"] is False
    assert result["active_authority"]=="NOT_AUTHORIZED"
    assert "access_token" not in str(result)
    assert "api_key" not in str(result)


@pytest.mark.parametrize("mutate",[
    "wrong_source","wrong_case","model_exit_zero","native_timed_out",
    "native_failure_not_systemexit","provider_called","rollback_failed",
    "auth_changed","plugin_not_restored","process_alive",
    "original_provider_forged","original_H4B_physical","H1_unknown_cleared",
    "native_session_present","original_target_created",
    "user_H4B_history_altered","sqlite_drift","observer_appeared",
])
def test_forged_or_modified_H4C_original_cannot_be_marked_safely_blocked(mutate):
    d=list(deepcopy(fixture()))
    o,u,r,owned,budget,other=d
    if mutate=="wrong_source":o["candidate_source_sha"]="0"*40
    elif mutate=="wrong_case":o["run_id"]="h4b_missing_read"
    elif mutate=="model_exit_zero":o["native_child_exit_code"]=0
    elif mutate=="native_timed_out":o["native_child_timed_out"]=True
    elif mutate=="native_failure_not_systemexit":u["failure"]="other"
    elif mutate=="provider_called":budget["attempted_new"]=1
    elif mutate=="rollback_failed":r["status"]="BLOCKED"
    elif mutate=="auth_changed":r["credential_metadata_unchanged"]=False
    elif mutate=="plugin_not_restored":r["plugin_private_state_restored"]=False
    elif mutate=="process_alive":owned["statuses"]["native"]="LIVE_EXACT_OWNER"
    elif mutate=="original_provider_forged":budget["ledger_digest_sha256"]="0"*64
    elif mutate=="original_H4B_physical":budget["reserved_original_h4b"]=1
    elif mutate=="H1_unknown_cleared":budget["historic_h1_unresolved"]=0
    elif mutate=="native_session_present":other["original_sessions"]=1
    elif mutate=="original_target_created":other["target_absent"]=False
    elif mutate=="user_H4B_history_altered":other["other_H4B_untouched"]=False
    elif mutate=="sqlite_drift":other["baseline_same"]=False
    elif mutate=="observer_appeared":other["observer_absent"]=False
    with pytest.raises(report.H4CIncidentBlocked):
        adjudicate(d)


def test_original_verifier_is_readonly_with_no_paid_model_invocation():
    source=Path(report.__file__).read_text()
    assert "run_oneshot(" not in source
    assert "subprocess.Popen(" not in source
    assert "subprocess.run(" not in source
    assert "new_provider_calls" in source
