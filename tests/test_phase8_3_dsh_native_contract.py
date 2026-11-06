"""Synthetic DSH SDK typed event contract with no Provider/Agent calls."""
from copy import deepcopy
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from phase8_3_dsh_native_contract import (
    verify_native_lifecycle, DshNativeEvidenceBlocked, SCENARIOS,
)

def frame(kind,data,sid="SYNTHETIC_SESSION_ONLY"):
    return {"method":"session.event",
            "params":{"sessionId":sid,"event":{"type":kind,"data":data}}}

def synthetic_native(*,failed=False):
    return [
        frame("turn/start",{"turn":1}),
        frame("tool/call",{"turn":1,"callId":"SYNTHETIC_CALL","name":"read"}),
        frame("tool/result",{"turn":1,"message":{
            "source":{"callId":"SYNTHETIC_CALL"},"isError":failed,
        }}),
        frame("turn/end",{"turn":1,"reason":{"kind":"completed"}}),
    ]

@pytest.mark.parametrize("scenario,failed",list(SCENARIOS.items()))
def test_dsh_offline_native_frame_lifecycle_requires_typed_failure(scenario,failed):
    result=verify_native_lifecycle(synthetic_native(failed=failed),scenario=scenario)
    assert result["tool_failure_is_sdk_typed"] is failed
    assert result["one_read_tool_call"] is True
    assert result["tool_call_and_result_id_match"] is True
    assert result["native_adapter_http_exact_join"]=="NOT_ESTABLISHED"
    assert result["raw_tool_result_matches_disposable_file"]=="NOT_ESTABLISHED"
    assert result["main_provider_requests"]==0
    assert result["active_authority"]=="NOT_AUTHORIZED"
    assert "SYNTHETIC_SESSION_ONLY" not in str(result)

@pytest.mark.parametrize("change",[
    "wrong_name","wrong_result_id","duplicate","missing_start",
    "cross_session","cross_turn","wrong_order","untyped_failure",
    "false_failure","bad_turn_close",
])
def test_dsh_missing_crosslinked_or_forged_event_fails_closed(change):
    data=deepcopy(synthetic_native(failed=True))
    if change=="wrong_name":
        data[1]["params"]["event"]["data"]["name"]="write"
    elif change=="wrong_result_id":
        data[2]["params"]["event"]["data"]["message"]["source"]["callId"]="wrong"
    elif change=="duplicate":data.append(deepcopy(data[2]))
    elif change=="missing_start":data.pop(0)
    elif change=="cross_session":data[2]["params"]["sessionId"]="other"
    elif change=="cross_turn":data[3]["params"]["event"]["data"]["turn"]=2
    elif change=="wrong_order":data[1],data[2]=data[2],data[1]
    elif change=="untyped_failure":
        data[2]["params"]["event"]["data"]["message"]["isError"]="true"
    elif change=="false_failure":
        data[2]["params"]["event"]["data"]["message"]["isError"]=False
    elif change=="bad_turn_close":
        data[3]["params"]["event"]["data"]["reason"]["kind"]="tool-only"
    with pytest.raises(DshNativeEvidenceBlocked):
        verify_native_lifecycle(data,scenario="d4_missing_read")
