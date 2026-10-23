"""H3 actual native/HTTP/Provider adjudicator, synthetic tamper regressions.

These tests NEVER run a main Provider or native Agent. All fixtures are
invented; no original H3 private files, keys, Session IDs, or prompts.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_verify_real_h3 as h3


def fixture():
    native={
        "code_sha":h3.FROZEN_H3,"run_id":h3.RUN_ID,
        "platform":"hermes","mode":"shadow","scenario":"read_nonce",
        "main_model":"stepfun/step-5-preview",
        "process_exit_code":0,"timed_out":False,
        "input_unchanged":True,
        "read_proof":{"final_answer_matches_nonce":True},
        "provider_calls_counted_at_proxy":2,
        "provider_global_used":8,
        "elapsed_seconds":13.5,
        "usage":{"api_calls":2,"completed":True,"failed":False,
                 "input_tokens":7250,"output_tokens":95},
    }
    prior={
        "source_sha":h3.FROZEN_H3,
        "run_id":h3.RUN_ID,
        "h3_scoped_verdict":"PASS_SCOPED",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_REQUEST",
        "profile_off_restored":True,
        "background_title_llm_upgrade":"DISABLED_TEST_HOME_ONLY",
        "provider_physical_ledger":{"ledger_digest_sha256":h3.H3_LEDGER_SHA},
    }
    physical=[]
    for slot in range(1,9):
        run="h1_read_off" if slot<=3 else "h2_read_shadow" if slot<=6 else h3.RUN_ID
        physical.extend((
            {"kind":"reserved","run":run,"slot":slot},
            {"kind":"attempted","run":run,"slot":slot},
        ))
        if slot!=1:
            physical.extend((
                {"kind":"responded","run":run,"slot":slot,"http_status":200},
                {"kind":"result","run":run,"slot":slot,
                 "http_status":200,"duration_ms":40.0},
            ))
    group={
        "reserved_global":8,"reserved_h1":3,"reserved_h2":3,
        "reserved_new":2,"attempted_new":2,"responded_new":2,
        "unknown_new":0,"finalized_new":2,"historic_h1_unresolved":1,
        "new_run_status":"SCOPE_COMPLETE",
        "overall_phase_8_3a_integrity":"BLOCKED_HISTORICAL_UNRESOLVED",
    }
    oracle={"valid":True}
    for k in (
        "native_tool_call_result_id_paired",
        "original_file_bytes_match_tool",
        "final_answer_matches_original",
        "nonce_absent_from_prompt",
        "native_provider_route_confirmed",
    ):oracle[k]=True
    adapter=[
        {"native_stage":"tool_result","action_status":"failed_open"},
        {"native_stage":"turn_end","action_status":"failed_open"},
    ]
    joined={
        "status":"PASS","native_http_pairs_verified":2,
        "adapter_completion_observations":2,"issues":[],
    }
    http=[
        {
            "http_status":503,
            "backend":None,"decision_source":None,
            "path":"/v1/workflows/completion-gate",
            "response_matches_request_id":None,
        }
        for _ in (1,2)
    ]
    return native,prior,physical,group,oracle,adapter,joined,http


def score(*args):
    return h3.analyze(*args,digest=h3.H3_LEDGER_SHA)


def test_real_h3_success_fixtures_support_scoped_failopen_not_active():
    r=score(*fixture())
    assert r["h3_scoped_qualification"]=="PASS_SCOPED"
    assert r["phase8_3a_overall"]=="BLOCKED_HISTORICAL_H1_UNRESOLVED"
    assert r["native_task"]["outcome"]=="PASS_SCOPED"
    assert r["shadow_runtime_down"]["observed_completion_HTTP_503"]==2
    assert r["shadow_runtime_down"]["adapter_failed_open_observations"]==2
    assert r["shadow_runtime_down"]["native_adapter_http_exact_pairs"]==2
    assert r["shadow_runtime_down"]["active_action_allowed"] is False
    assert r["provider_physical"]["H3_attempted"]==2
    assert r["provider_physical"]["H3_unresolved"]==0
    assert r["provider_physical"]["H3_physically_unattributed"]==0
    assert r["provider_physical"]["original_h1_unresolved"]==1
    assert r["title_generation_test_home"]["hypothesis_status"].endswith("NOT_CAUSALLY_PROVEN")
    assert r["actual_StepFun_plan_credit_debit"]=="UNKNOWN"
    assert r["real_agent_cost_saving"]=="NOT_MEASURED"
    assert r["active_authority"]=="NOT_AUTHORIZED"
    assert "access_token" not in json.dumps(r)


@pytest.mark.parametrize("mutation",(
    "source","native_fail","wrong_oracle","unexpected_503",
    "adapter_missing","bad_join","h1_unknown_forged",
    "provider_non200","no_h3_terminal","extra_attempt",
    "no_title_disable","not_restored_off","wrong_main_calls",
))
def test_private_h3_evidence_tampering_is_blocked(mutation):
    parts=list(deepcopy(fixture()))
    native,prior,physical,group,oracle,adapter,joined,http=parts
    if mutation=="source":native["code_sha"]="0"*40
    elif mutation=="native_fail":native["process_exit_code"]=1
    elif mutation=="wrong_oracle":oracle["final_answer_matches_original"]=False
    elif mutation=="unexpected_503":http[0]["http_status"]=200
    elif mutation=="adapter_missing":adapter[0]["action_status"]="observed"
    elif mutation=="bad_join":joined["native_http_pairs_verified"]=1
    elif mutation=="h1_unknown_forged":
        physical.extend((
            {"kind":"responded","run":"h1_read_off","slot":1,"http_status":200},
            {"kind":"result","run":"h1_read_off","slot":1,"http_status":200},
        ))
    elif mutation=="provider_non200":
        next(x for x in physical if x["run"]==h3.RUN_ID and
             x["kind"]=="responded")["http_status"]=429
    elif mutation=="no_h3_terminal":
        physical[:]=[r for r in physical if not (
            r["run"]==h3.RUN_ID and r["slot"]==8 and r["kind"]=="responded")]
    elif mutation=="extra_attempt":group["attempted_new"]=3
    elif mutation=="no_title_disable":prior["background_title_llm_upgrade"]="ENABLED"
    elif mutation=="not_restored_off":prior["profile_off_restored"]=False
    elif mutation=="wrong_main_calls":native["usage"]["api_calls"]=3
    with pytest.raises(h3.H3EvidenceError):
        score(*parts)


def test_observer_extra_event_cannot_be_discarded():
    parts=list(deepcopy(fixture()))
    parts[-1].append(deepcopy(parts[-1][0]))
    with pytest.raises(h3.H3EvidenceError):
        score(*parts)


def test_history_based_extraction_requires_exact_two_hmac_refs(tmp_path,monkeypatch):
    monkeypatch.setattr(h3,"TEST_HOME",tmp_path)
    plugin=tmp_path/"plugin-data"/"isolated"
    plugin.mkdir(parents=True)
    h2ref="2"*32
    h3refs=["a"*32,"b"*32]
    state={
        "completion_loop_probe_history":[
            {"decision_request_ref":h2ref,"gate":"completion","mode":"shadow"},
            {"decision_request_ref":h3refs[0],"gate":"completion","mode":"shadow",
             "native_stage":"tool_result","action_status":"failed_open"},
        ],
        "completion_shadow_history":[
            {"decision_request_ref":h3refs[1],"gate":"completion","mode":"shadow",
             "native_stage":"turn_end","action_status":"failed_open"},
        ],
    }
    (plugin/"state.json").write_text(json.dumps(state))
    http=[{"decision_request_ref":x} for x in h3refs]
    selected=h3.h3_adapter_from_current_home(http)
    assert {x["decision_request_ref"] for x in selected}==set(h3refs)
    assert h2ref not in str(selected)
    state["completion_shadow_history"].append(deepcopy(state["completion_shadow_history"][0]))
    (plugin/"state.json").write_text(json.dumps(state))
    with pytest.raises(h3.H3EvidenceError,match="missing/duplicate"):
        h3.h3_adapter_from_current_home(http)
