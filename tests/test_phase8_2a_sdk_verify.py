"""Synthetic VERIFIER tests only. These fixtures are not native Agent evidence."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_sdk_verify import verify, FROZEN_NATIVE_SHA

A = "p82sdk-main"
B = "p82sdk-side"


def _j(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False))


def _jl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(v,ensure_ascii=False) for v in rows) + "\n")


def _frame(sid: str, turn: int, kind: str, *, callid: str = "read-1",
           marker: str = "", failed: bool = False) -> dict:
    data: dict = {"turn": turn}
    if kind == "tool/call":
        data.update({"name": "read", "callId": callid})
    if kind == "tool/result":
        data["message"] = {"isError": failed,"source": {"callId": callid},
                           "content": [{"type": "text", "text": marker}]}
    if kind == "assistant/message":
        data["message"] = {"content": [{"type": "text", "text": marker}]}
    if kind == "turn/end":
        data["reason"] = {"kind": "completed"}
    return {"jsonrpc": "2.0", "method": "session.event", "params": {
        "sessionId": sid, "event": {"type": kind, "data": data}}}


def _flow(sid: str, turn: int, marker: str, *, failed: bool = False) -> list[dict]:
    return [
        _frame(sid,turn,"turn/start"),
        _frame(sid,turn,"tool/call"),
        _frame(sid,turn,"tool/result",marker=marker,failed=failed),
        _frame(sid,turn,"assistant/message",marker=marker),
        _frame(sid,turn,"turn/end"),
    ]


def _rpc(i: int) -> dict:
    return {"jsonrpc": "2.0", "id":i, "result":{}}


def _fixture(root: Path) -> None:
    root.mkdir(exist_ok=True)
    _j(root/"manifest.private.json", {
        "frozen_executable_source":FROZEN_NATIVE_SHA,
        "main_model":"stepfun/step-5-preview",
        "provider_budget_total":12,
        "pinned_dsh":"z"*40,
    })
    resident = root/"runs/sdk_resident"
    resident.mkdir(parents=True)
    (resident/"input_primary.txt").write_text("P82A_NATIVE_SDK_PRIMARY_SYNTHETIC")
    (resident/"input_parallel.txt").write_text("P82A_NATIVE_SDK_SIDE_SYNTHETIC")
    # Deliberate A2/B1 active-turn overlap; no claim of true concurrent tool execution.
    frames=[_rpc(1),_rpc(2),*_flow(A,1,"failed",failed=True),
        _frame(A,2,"turn/start"),_rpc(3),
        _frame(B,1,"turn/start"),_rpc(4),
        *_flow(A,2,"P82A_NATIVE_SDK_PRIMARY_SYNTHETIC")[1:],
        *_flow(B,1,"P82A_NATIVE_SDK_SIDE_SYNTHETIC")[1:],
        _rpc(5)]
    _jl(resident/"sdk_events.private.jsonl",frames)
    _j(resident/"result.private.json",{"test_status":"SCOPED_NATIVE_RESIDENT_PROCESS_PASS",
                                             "provider_calls":6,"same_os_pid_process":True})
    for mode in ("off","down"):
        folder=root/"runs"/("dsh_sdk_"+mode)
        folder.mkdir(parents=True)
        content="P82A_SDK_COMPARE_READ_"+mode.upper()+"_FAKE"
        (folder/"input.txt").write_text(content)
        _jl(folder/"sdk_events.private.jsonl",[_rpc(1),_rpc(2),*_flow("p82sdk_"+mode,1,content),_rpc(3)])
        _j(folder/"independent_summary.private.json",{
            "tool_ids_paired":True, "native_tool_result_success":True,
            "final_message_matches_content":True,"sdk_process_exit_code":0,
            "provider_requests":2,"gate_events_during_run":0 if mode=="off" else 2})
    providers=[]
    for slot in range(1,11):
        name="dsh_sdk_resident" if slot<=6 else "dsh_sdk_off" if slot<=8 else "dsh_sdk_down"
        providers.extend(({"kind":"reserved","slot":slot,"run":name},
                          {"kind":"result","slot":slot,"run":name,"http_status":200}))
    _jl(root/"provider_calls.private.jsonl",providers)
    collector=([{"workflow":"completion_gate","http_status":200,"backend":"mlx","decision_source":"model"}]*6
        + [{"workflow":"retry_escalation_gate","http_status":200,"backend":"rule","decision_source":"rule"}]
        + [{"http_status":503},{"http_status":503}])
    _jl(root/"collector_events.private.jsonl",collector)


def test_synthetic_complete_fixture_passes_only_scoped_claim(tmp_path):
    _fixture(tmp_path)
    result=verify(tmp_path)
    assert result["status"]=="SCOPED_DSH_NATIVE_SDK_RESIDENT_AND_OFF_DOWN_PASS"
    assert result["phase8_2a_engineering"]=="BLOCKED"
    assert result["sdk_two_distinct_sessions_start_overlapped"] is True
    assert result["provider_network_budget"]["actual_reserved_and_completed"]==10


def test_synthetic_missing_native_event_fails_closed(tmp_path):
    _fixture(tmp_path)
    p=tmp_path/"runs/sdk_resident/sdk_events.private.jsonl"
    events=[json.loads(x) for x in p.read_text().splitlines()]
    events=[x for x in events if not (x.get("params",{}).get("sessionId")==B
        and x.get("params",{}).get("event",{}).get("type")=="tool/result")]
    _jl(p,events)
    with pytest.raises(ValueError,match="exactly one start/end"):
        verify(tmp_path)


def test_synthetic_nonoverlapping_turn_starts_rejected(tmp_path):
    _fixture(tmp_path)
    p=tmp_path/"runs/sdk_resident/sdk_events.private.jsonl"
    events=[json.loads(x) for x in p.read_text().splitlines()]
    starts=[x for x in events if x.get("params",{}).get("sessionId")==B
      and x.get("params",{}).get("event",{}).get("type")=="turn/start"]
    assert len(starts)==1
    events.remove(starts[0])
    # Move B's Turn start to after the primary second Turn ends.
    idx=next(i for i,x in enumerate(events) if x.get("params",{}).get("sessionId")==A
         and x.get("params",{}).get("event",{}).get("type")=="turn/end"
         and x.get("params",{}).get("event",{}).get("data",{}).get("turn")==2)
    events.insert(idx+1,starts[0])
    _jl(p,events)
    with pytest.raises(ValueError,match="was not active"):
        verify(tmp_path)


def test_synthetic_bad_provider_denominator_rejected(tmp_path):
    _fixture(tmp_path)
    p=tmp_path/"provider_calls.private.jsonl"
    rows=[json.loads(x) for x in p.read_text().splitlines()]
    _jl(p,rows[:-1])
    with pytest.raises(ValueError,match="denominator mismatch"):
        verify(tmp_path)


def test_synthetic_mismatched_tool_content_rejected(tmp_path):
    _fixture(tmp_path)
    p=tmp_path/"runs/dsh_sdk_down/input.txt"
    p.write_text("P82A_SDK_COMPARE_READ_DOWN_CHANGED")
    with pytest.raises(ValueError,match="independently contain file content"):
        verify(tmp_path)


def test_synthetic_off_mode_runtime_request_rejected(tmp_path):
    _fixture(tmp_path)
    p=tmp_path/"collector_events.private.jsonl"
    rows=[json.loads(x) for x in p.read_text().splitlines()]
    rows[0]["http_status"]=503
    _jl(p,rows)
    with pytest.raises(ValueError,match="Laya Completion inference"):
        verify(tmp_path)
