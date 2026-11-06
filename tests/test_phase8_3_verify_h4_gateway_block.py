"""Synthetic H4 admission incident proof: never mistake failed Gateway startup for Agent."""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import phase8_3_verify_h4_gateway_block as h4


def fixture():
    native={
        "code_sha":h4.FROZEN_H4,"run_id":h4.H4,
        "platform":"hermes","mode":"shadow",
        "scenario":"read_missing","process_exit_code":1,
        "provider_calls_counted_at_proxy":0,
        "h4_missing_file_absent":True,
        "usage":{},"timed_out":False,
    }
    outer={
        "source_sha":h4.FROZEN_H4,"run_id":h4.H4,
        "native_agent_exit_code":0,
        "h4_scoped_verdict":"PARTIAL_OR_BLOCKED",
        "profile_restored_off":True,
        "physical_provider":{"reserved_new":0},
    }
    return native,outer


def analyze(native=None,outer=None,**kwargs):
    defaults={
        "provider_sha":h4.H3_ORIGINAL_SHA256,
        "native_sessions":0,
        "gateway_stderr":"Error: Gateway could not start: the host gateway already serves profile 'default'",
        "observer_exists":False,"original_absent":True,
    }
    defaults.update(kwargs)
    x,y=fixture()
    return h4.analyze(native or x,outer or y,**defaults)


def test_real_H4_gateway_admission_is_not_real_native_failure_evidence():
    report=analyze()
    assert report["h4_status"]=="BLOCKED_BEFORE_NATIVE_AGENT_AND_PROVIDER"
    assert report["real_provider_physical_attempts_h4"]==0
    assert report["actual_native_session_created"] is False
    assert report["actual_native_read_file_invoked"] is False
    assert report["original_wrapper_process_exit"]==0
    assert report["original_hermes_process_exit"]==1
    assert report["wrapper_misreported_agent_failure"] is True
    assert report["automatic_h4_rerun_permitted"] is False
    assert report["provider_ledger_global_reserved"]==8
    assert report["historical_H1_unresolved"]==1
    assert report["production_gateway_modified"] is False


@pytest.mark.parametrize("change",[
    "native_success","native_provider_call","native_tool_succeeded",
    "different_sha","prior_pass","outer_exit_fixed",
    "no_original_gateway_reason","unexpected_native_session",
    "different_global_provider_history","H4_observer_present",
    "target_exists","test_home_not_restored",
])
def test_gateway_incident_cannot_hide_real_task_or_unknown_provider_activity(change):
    n,o=deepcopy(fixture())
    args={}
    if change=="native_success":n["process_exit_code"]=0
    elif change=="native_provider_call":n["provider_calls_counted_at_proxy"]=1
    elif change=="native_tool_succeeded":n["h4_missing_file_absent"]=False
    elif change=="different_sha":o["source_sha"]="0"*40
    elif change=="prior_pass":o["h4_scoped_verdict"]="PASS_SCOPED"
    elif change=="outer_exit_fixed":o["native_agent_exit_code"]=3
    elif change=="no_original_gateway_reason":args["gateway_stderr"]="permission denied"
    elif change=="unexpected_native_session":args["native_sessions"]=1
    elif change=="different_global_provider_history":args["provider_sha"]="0"*64
    elif change=="H4_observer_present":args["observer_exists"]=True
    elif change=="target_exists":args["original_absent"]=False
    elif change=="test_home_not_restored":o["profile_restored_off"]=False
    with pytest.raises(h4.H4AdmissionBlocked):
        analyze(n,o,**args)


def test_direct_h4_native_engine_discovery_is_offline_only():
    src=(Path(__file__).resolve().parents[1]/
         "scripts/phase8_3_hermes_direct_entry_preflight.py").read_text()
    assert "--check-offline" in src
    assert "run_oneshot" in src
    assert "_run_agent" in src
    assert "from run_agent import AIAgent" in src
    assert "future_H4_separate_run_authorized" in src
    assert "actual_native_Agent_task_executed" in src
    assert "real_model_provider_requests" in src
    assert "--execute-real-step-plan" not in src
