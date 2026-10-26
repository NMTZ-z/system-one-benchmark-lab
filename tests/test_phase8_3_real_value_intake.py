"""Real historic StepFun provenance checks, no real models or private reads."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import phase8_3_real_value_intake as rv


def originals():
    return rv.historical_inputs()


def test_public_original_three_tasks_do_not_become_decision_oracles():
    result=rv.assess_historical_data(originals())
    assert result["historical_native_task_successes_with_published_verification"]==3
    assert result["historical_raw_native_evidence_rechecked_in_this_audit"] is False
    assert result["recorded_real_local_decision_observations"]==2
    assert result["separately_adjudicated_real_decision_gold_count"]==0
    assert result["qualified_rules_vs_laya_real_pairs"]==0
    assert result["real_decision_correctness_benchmark"]=="NOT_ESTABLISHED"
    assert result["provider_attempts_historical"]==8
    assert result["provider_HTTP_200_terminal_historical"]==7
    assert result["provider_outcome_unknown_historical"]==1
    assert result["excluded_synthetic_stock_shadow_from_real_denominator"] is True
    assert result["new_model_inferences_for_this_audit"]==0
    assert result["new_provider_calls_for_this_audit"]==0


@pytest.mark.parametrize("who,mutation",[
    ("H1","unknown"),("H1","pretend_all_terminal"),("H1","success_false"),
    ("H1","off_to_shadow"),("H2","fake_local_model"),("H2","wrong_causal_join"),
    ("H2","budget_refund"),("H2","missing_h1_unknown"),("H3","wrong_original_ledger"),
    ("H3","changed_503"),("H3","fake_H3_success"),("H3","canary_authorized"),
])
def test_unsafe_or_conflicted_real_evidence_is_rejected(who,mutation):
    data=copy.deepcopy(originals())
    if mutation=="unknown":data[who]["physical_request_budget"]["attempted_unresolved"]=0
    elif mutation=="pretend_all_terminal":data[who]["physical_request_budget"]["provider_responded"]=3
    elif mutation=="success_false":data[who]["native_task"]["original_file_bytes_verified"]=False
    elif mutation=="off_to_shadow":data[who]["system_one_mode"]="shadow"
    elif mutation=="fake_local_model":data[who]["h2_local_laya"]["mlx_model_decision_observed"]=3
    elif mutation=="wrong_causal_join":data[who]["h2_local_laya"]["strict_native_adapter_http_joined"]=1
    elif mutation=="budget_refund":data[who]["h2_physical_provider"]["h2_physical_attempts"]=2
    elif mutation=="missing_h1_unknown":data[who]["h2_physical_provider"]["historical_h1_unresolved"]=0
    elif mutation=="wrong_original_ledger":data[who]["provider_physical"]["H3_original_ledger_sha256"]="0"*64
    elif mutation=="changed_503":data[who]["shadow_runtime_down"]["observed_completion_HTTP_503"]=1
    elif mutation=="fake_H3_success":data[who]["native_task"]["tool_bytes_match_original_file"]=False
    elif mutation=="canary_authorized":data[who]["shadow_runtime_down"]["active_action_allowed"]=True
    with pytest.raises(rv.RealIntakeBlocked):
        rv.assess_historical_data(data)


def test_unlisted_cohort_cannot_be_mislabelled_real():
    with pytest.raises(rv.RealIntakeBlocked):
        rv.assess_historical_data({**originals(),"synthetic_shadow":{}})


def test_historical_public_digest_and_symlink_tamper_blocked(tmp_path):
    fixture=tmp_path/"results/processed";fixture.mkdir(parents=True)
    for _,(name,_) in rv.HISTORIC_FILES.items():
        (fixture/name).write_bytes((rv.ROOT/"results/processed"/name).read_bytes())
    assert rv.historical_inputs(tmp_path).keys()==rv.HISTORIC_FILES.keys()
    name=rv.HISTORIC_FILES["H2"][0]
    (fixture/name).write_bytes((fixture/name).read_bytes()+b"\n")
    with pytest.raises(rv.RealIntakeBlocked,match="historical_public_evidence_changed"):
        rv.historical_inputs(tmp_path)
    (fixture/name).unlink()
    (fixture/name).symlink_to(rv.ROOT/"results/processed"/name)
    with pytest.raises(rv.RealIntakeBlocked,match="missing_or_symlinked_history"):
        rv.historical_inputs(tmp_path)
