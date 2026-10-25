"""Independent H2 real-evidence adjudicator contract, SYNTHETIC ONLY tests.

The real H2 private evidence is never imported into a test fixture or PR.
Provider traffic cannot occur in these tests.
"""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_verify_real_h2 as v


def case():
    native={
        "run_id":v.RUN_ID,
        "code_sha":v.FROZEN_H2,
        "platform":"hermes","mode":"shadow",
        "scenario":"read_nonce",
        "main_model":"stepfun/step-5-preview",
        "process_exit_code":0,
        "timed_out":False,
        "input_unchanged":True,
        "read_proof":{"final_answer_matches_nonce":True},
        "provider_calls_counted_at_proxy":3,
        "provider_global_used":6,
        "elapsed_seconds":29.5,
        "usage":{"api_calls":2,"completed":True,"failed":False,
                 "input_tokens":7250,"output_tokens":500},
    }
    original={
        "source_sha":v.FROZEN_H2,
        "run_id":v.RUN_ID,
        "h2_scoped_verdict":"PASS_SCOPED",
        "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_UNRESOLVED",
        "provider_physical_ledger":{"ledger_digest_sha256":"mock_ledger_digest"},
    }
    physical=[]
    for slot in (1,2,3):
        physical.extend((
            {"kind":"reserved","slot":slot,"run":"h1_read_off"},
            {"kind":"attempted","slot":slot,"run":"h1_read_off"},
        ))
        if slot>=2:
            physical.extend((
                {"kind":"responded","slot":slot,"run":"h1_read_off","http_status":200},
                {"kind":"result","slot":slot,"run":"h1_read_off","http_status":200,"duration_ms":50.0},
            ))
    for slot in (4,5,6):
        physical.extend((
            {"kind":"reserved","slot":slot,"run":v.RUN_ID},
            {"kind":"attempted","slot":slot,"run":v.RUN_ID},
            {"kind":"responded","slot":slot,"run":v.RUN_ID,"http_status":200},
            {"kind":"result","slot":slot,"run":v.RUN_ID,"http_status":200,"duration_ms":55.0},
        ))
    group={
        "reserved_global":6,"reserved_h1":3,
        "reserved_new":3,"attempted_new":3,
        "responded_new":3,"unknown_new":0,"finalized_new":3,
        "historic_h1_unresolved":1,
        "new_run_status":"SCOPE_COMPLETE",
        "overall_phase_8_3a_integrity":"BLOCKED_HISTORICAL_UNRESOLVED",
    }
    oracle={"valid":True}
    for k in (
        "native_tool_call_result_identity",
        "tool_bytes_match_original",
        "agent_answer_matches_original",
        "input_absent_from_prompt",
        "native_provider_proxy_route",
    ):oracle[k]=True
    join={
        "status":"PASS",
        "native_http_pairs_verified":2,
        "adapter_completion_observations":2,
        "issues":[],
    }
    http=[
        {
            "http_status":200,"backend":"mlx","decision_source":"model",
            "response_matches_request_id":True,
            "path":"/v1/workflows/completion-gate",
        } for _ in range(2)
    ]
    return native,original,physical,group,oracle,join,http


def verify(*data):
    return v.analyze(*data,digest="mock_ledger_digest")


def test_h2_success_must_remain_scoped_and_cost_partially_attributed():
    obj=verify(*case())
    assert obj["h2_scoped_qualification"]=="PASS_SCOPED"
    assert obj["h2_local_laya"]["mlx_model_decision_observed"]==2
    assert obj["h2_local_laya"]["strict_native_adapter_http_joined"]==2
    assert obj["h2_physical_provider"]["h2_physical_attempts"]==3
    assert obj["h2_physical_provider"]["h2_provider_responses_HTTP_200"]==3
    assert obj["h2_physical_provider"]["h2_attempted_unresolved"]==0
    assert obj["h2_physical_provider"]["h2_physically_unattributed"]==1
    assert obj["h2_physical_provider"]["historical_h1_unresolved"]==1
    assert obj["h2_physical_provider"]["h2_budget_integrity"]=="PARTIAL_USAGE_ATTRIBUTION"
    assert obj["h2_physical_provider"]["historical_h1_budget_integrity"]=="BLOCKED"
    assert obj["real_agent_tokens_saved"]=="NOT_MEASURED"
    assert obj["real_agent_time_saved"]=="NOT_MEASURED"
    assert obj["active_authority"]=="NOT_AUTHORIZED"


@pytest.mark.parametrize("change",[
    lambda arr:arr[0].update(code_sha="0"*40),
    lambda arr:arr[0].update(process_exit_code=1),
    lambda arr:arr[0].update(mode="active"),
    lambda arr:arr[0].update(input_unchanged=False),
    lambda arr:arr[1].update(h2_scoped_verdict="PASS_GLOBAL"),
    lambda arr:arr[1].update(phase8_3a_overall="PASS"),
    lambda arr:arr[3].update(historic_h1_unresolved=0),
    lambda arr:arr[3].update(reserved_global=3),
    lambda arr:arr[3].update(responded_new=2),
    lambda arr:arr[4].update(tool_bytes_match_original=False),
    lambda arr:arr[5].update(native_http_pairs_verified=1),
    lambda arr:arr[5].update(issues=["identity_mismatch"]),
    lambda arr:arr[6][0].update(backend="rule"),
    lambda arr:arr[6][0].update(http_status=503),
    lambda arr:arr[6][0].update(response_matches_request_id=False),
])
def test_forged_or_missing_h2_provenance_must_block(change):
    args=list(deepcopy(case()))
    change(args)
    with pytest.raises((v.H2EvidenceError,ValueError)):
        verify(*args)


def test_absent_stepfun_terminal_record_still_blocks_even_if_agent_succeeds():
    args=list(deepcopy(case()))
    args[2]=[r for r in args[2]
             if not (r["run"]==v.RUN_ID and r["slot"]==4
                     and r["kind"]=="result")]
    with pytest.raises((v.H2EvidenceError,ValueError)):
        verify(*args)


def test_provider_usage_cannot_be_invented_or_mislabeled_as_savings():
    data=list(deepcopy(case()))
    result=verify(*data)
    assert result["h2_physical_provider"]["h2_provider_token_usage_source"]=="UNKNOWN"
    assert result["h2_physical_provider"]["h2_actual_subscription_credit_debit"]=="UNKNOWN"
    assert "api_key" not in str(result).lower()
    assert "access_token" not in str(result).lower()
    assert "P83_HERMES_NATIVE" not in str(result)


def test_exact_hidden_original_file_and_strict_identity_never_exported():
    result=verify(*case())
    assert "sessionId" not in result
    assert "native_call_id" not in result
    assert "raw_prompt" not in result


def test_h2_reverification_excludes_later_h3_events_only_by_original_hmac_refs(monkeypatch):
    import phase8_3_real_hermes_h2 as source
    import phase8_2b_native_correlate as strict
    expected={"a"*32,"b"*32}
    fake=[{"decision_request_ref":v,"gate":"completion"} for v in ("a"*32,"c"*32,"b"*32)]
    monkeypatch.setattr(source,"_plugin_observations",lambda:fake)
    seen={}
    def stub(_platform,_db,adapter,http,_key):
        seen["refs"]={x["decision_request_ref"] for x in adapter}
        return {"status":"PASS","native_http_pairs_verified":2,
                "adapter_completion_observations":2,"issues":[]}
    monkeypatch.setattr(strict,"correlate",stub)
    result=source._native_http_correlate(b"x"*32,[
        {"decision_request_ref":"a"*32},
        {"decision_request_ref":"b"*32},
    ])
    assert result["status"]=="PASS"
    assert seen["refs"]==expected


def test_h2_reverification_fails_closed_on_missing_or_repeated_historical_refs(monkeypatch):
    import phase8_3_real_hermes_h2 as source
    monkeypatch.setattr(source,"_plugin_observations",lambda:[
        {"decision_request_ref":"a"*32,"gate":"completion"},
        {"decision_request_ref":"a"*32,"gate":"completion"},
        {"decision_request_ref":"c"*32,"gate":"completion"},
    ])
    outcome=source._native_http_correlate(b"k"*32,[
        {"decision_request_ref":"a"*32},
        {"decision_request_ref":"b"*32},
    ])
    assert outcome["status"]=="BLOCKED"
    assert outcome["native_http_pairs_verified"]==0
    assert outcome["cause"]=="missing_or_duplicate_H2_adapter_reference"
