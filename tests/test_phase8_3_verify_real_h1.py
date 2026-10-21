"""Offline synthetic audit fixtures for private H1 real-evidence verifier."""
from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase8_3_verify_real_h1 as verifier


def _cases():
    native={
        "code_sha":verifier.SOURCE_H1,
        "run_id":verifier.RUN_ID,
        "platform":"hermes",
        "mode":"off",
        "scenario":"read_nonce",
        "main_model":"stepfun/step-5-preview",
        "process_exit_code":0,
        "timed_out":False,
        "input_unchanged":True,
        "read_proof":{"final_answer_matches_nonce":True},
        "gate_http_statuses":[],
        "usage":{"api_calls":2,"completed":True,"failed":False,
                 "input_tokens":7000,"output_tokens":300},
        "provider_calls_counted_at_proxy":3,
    }
    private={
        "source_sha":verifier.SOURCE_H1,
        "transport":{"attempted":3},
        "independent_native":{"valid":True},
    }
    rows=[]
    for slot in (1,2,3):
        rows.extend(({"kind":"reserved","run":verifier.RUN_ID,"slot":slot},
                     {"kind":"attempted","run":verifier.RUN_ID,"slot":slot}))
        if slot>1:
            rows.extend(({"kind":"responded","run":verifier.RUN_ID,"slot":slot,
                          "http_status":200},
                         {"kind":"result","run":verifier.RUN_ID,"slot":slot,
                          "http_status":200,"duration_ms":100.0}))
    oracle={"valid":True}
    for key in ("native_read_result_paired", "original_file_matches_native_tool",
                "agent_final_matches_original_file", "native_provider_route_confirmed"):
        oracle[key]=True
    return native,private,rows,oracle


def test_h1_real_fixture_cannot_overstate_unfinalized_physical_provider_slot():
    native, private, rows, oracle=_cases()
    r=verifier.analyze(native,private,rows,oracle,evidence_hash="a"*64)
    assert r["native_task"]["task_result"]=="PASS_SCOPED"
    assert r["phase8_3_real_native_acceptance"]=="BLOCKED_BUDGET_RECONCILIATION"
    assert r["physical_request_budget"]["budget_integrity"]=="BLOCKED"
    assert r["physical_request_budget"]["attempted"]==3
    assert r["physical_request_budget"]["provider_responded"]==2
    assert r["physical_request_budget"]["attempted_unresolved"]==1
    assert r["physical_request_budget"]["unattributed_requests"]==1
    assert r["provider_response_codes"]==[200,200]
    assert r["permission_to_run_more_provider_tasks"] is False
    assert r["subscription_plan_debit"]=="UNKNOWN"
    assert r["real_agent_savings"]=="NOT_MEASURED"
    assert r["active_authority"]=="NOT_AUTHORIZED"
    assert "api_key" not in str(r).lower()
    assert "access_token" not in str(r).lower()


def test_responded_slots_do_not_pretend_measured_billing():
    native,private,rows,oracle=_cases()
    rows.extend(({"kind":"responded","run":verifier.RUN_ID,"slot":1,
                  "http_status":200},
                 {"kind":"result","run":verifier.RUN_ID,"slot":1,
                  "http_status":200,"duration_ms":75.0}))
    r=verifier.analyze(native,private,rows,oracle,evidence_hash="b"*64)
    assert r["physical_request_budget"]["attempted_unresolved"]==0
    assert r["physical_request_budget"]["provider_responded"]==3
    assert r["physical_request_budget"]["budget_integrity"]=="PARTIAL"
    assert r["subscription_plan_debit"]=="UNKNOWN"
    assert r["phase8_3_real_native_acceptance"]=="PARTIAL_COST_UNKNOWN"


@pytest.mark.parametrize("field,value",[
    ("source","0"*40),("mode","shadow"),("exit",1),("wrong_platform","dsh"),
])
def test_false_native_evidence_rejected(field,value):
    native,private,rows,oracle=_cases()
    if field=="source":native["code_sha"]=value
    elif field=="mode":native["mode"]=value
    elif field=="exit":native["process_exit_code"]=value
    elif field=="wrong_platform":native["platform"]=value
    with pytest.raises(verifier.H1EvidenceError):
        verifier.analyze(native,private,rows,oracle,evidence_hash="a"*64)


def test_unmatched_or_fabricated_native_file_proof_rejected():
    native,private,rows,oracle=_cases()
    oracle["original_file_matches_native_tool"]=False
    with pytest.raises(verifier.H1EvidenceError):
        verifier.analyze(native,private,rows,oracle,evidence_hash="c"*64)


def test_wrong_ledger_run_id_or_count_never_passes():
    native,private,rows,oracle=_cases()
    rows[0]["run"]="unexpected_run"
    with pytest.raises((verifier.H1EvidenceError,ValueError)):
        verifier.analyze(native,private,rows,oracle,evidence_hash="a"*64)
