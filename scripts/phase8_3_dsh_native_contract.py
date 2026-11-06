#!/usr/bin/env python3
"""Offline structural validation for actual DSH SDK native tool frames.

The DSH SDK emits typed session.event frames with turn/start, tool/call,
tool/result and turn/end. This validator requires exact call/result identity,
one native read tool and a typed isError outcome appropriate to the
predeclared scenario. Tool bytes/final answer are NEVER inferred from
SDK event shape; independently check the disposable original input later.
No Agent execution, model traffic, credential access or production state.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

SCENARIOS = {
    "d1_read_off":False,
    "d2_read_shadow":False,
    "d3_runtime_down":False,
    "d4_missing_read":True,
}


class DshNativeEvidenceBlocked(ValueError):
    pass


def verify_native_lifecycle(frames: list[dict[str,Any]], *, scenario: str) -> dict[str,Any]:
    if scenario not in SCENARIOS:
        raise DshNativeEvidenceBlocked("unapproved DSH native scenario")
    if not isinstance(frames,list) or not 4<=len(frames)<=256:
        raise DshNativeEvidenceBlocked("native event count invalid")
    events=[]
    for frame in frames:
        if not isinstance(frame,dict):
            raise DshNativeEvidenceBlocked("malformed DSH SDK frame")
        if frame.get("method")!="session.event":
            continue
        params=frame.get("params")
        event=params.get("event") if isinstance(params,dict) else None
        if not isinstance(event,dict):
            raise DshNativeEvidenceBlocked("native SDK event fields absent")
        kind=event.get("type")
        if kind not in {"turn/start","turn/end","tool/call","tool/result"}:
            continue
        sid=params.get("sessionId")
        data=event.get("data")
        if (not isinstance(sid,str) or not 1<=len(sid)<=256
                or not isinstance(data,dict) or type(data.get("turn")) is not int
                or data["turn"]<1):
            raise DshNativeEvidenceBlocked("native Session/Turn identifiers missing")
        events.append((sid,data["turn"],kind,data))
    if len(events)!=4 or Counter(event[2] for event in events)!={
        "turn/start":1,"tool/call":1,"tool/result":1,"turn/end":1,
    }:
        raise DshNativeEvidenceBlocked("DSH native task has missing/duplicate event")
    first=events[0]
    if any(x[:2]!=first[:2] for x in events):
        raise DshNativeEvidenceBlocked("cross-session or cross-turn native evidence")
    kinds=[x[2] for x in events]
    if kinds!=["turn/start","tool/call","tool/result","turn/end"]:
        raise DshNativeEvidenceBlocked("native event lifecycle order invalid")
    caller,returned=events[1][3],events[2][3]
    if caller.get("name")!="read":
        raise DshNativeEvidenceBlocked("native DSH task used unapproved tool")
    call=caller.get("callId")
    source=returned.get("message")
    src=source.get("source") if isinstance(source,dict) else None
    if (not isinstance(call,str) or not 1<=len(call)<=256
            or not isinstance(src,dict) or src.get("callId")!=call):
        raise DshNativeEvidenceBlocked("native DSH call/result IDs not paired")
    is_error=source.get("isError")
    if type(is_error) is not bool or is_error is not SCENARIOS[scenario]:
        raise DshNativeEvidenceBlocked("native typed tool result failed scenario classification")
    reason=events[3][3].get("reason")
    if (not isinstance(reason,dict)
            or reason.get("kind") not in {"completed","stopped"}):
        raise DshNativeEvidenceBlocked("native DSH turn completion reason missing")
    return {
        "schema":"local-system-one/phase8_3-dsh-native-event-v1",
        "scenario":scenario,
        "native_sdk_event_count":4,
        "one_read_tool_call":True,
        "tool_call_and_result_id_match":True,
        "tool_failure_is_sdk_typed":is_error,
        "native_session_and_turn_identity_consistent":True,
        "native_turn_closed":True,
        "raw_tool_result_matches_disposable_file":"NOT_ESTABLISHED",
        "Agent_final_answer_truthful":"NOT_ESTABLISHED",
        "native_adapter_http_exact_join":"NOT_ESTABLISHED",
        "main_provider_requests":0,
        "active_authority":"NOT_AUTHORIZED",
    }
