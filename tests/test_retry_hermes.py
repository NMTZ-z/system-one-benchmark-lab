"""Hermes Phase 8C Retry Shadow hook tests; no production plugin installation."""

from __future__ import annotations

import threading
import time

from test_hermes_system_one_plugin import FakeContext, load_plugin


def _ctx(enabled=True):
    return FakeContext(
        "shadow",
        search_gate_enabled=False,
        model_tier_gate_enabled=False,
        notification_gate_enabled=False,
        completion_gate_enabled=False,
        retry_escalation_gate_enabled=enabled,
    )


def _failed(tool="write_file", *, turn="turn-1", call="tool-1", status="error"):
    return {
        "turn_id": turn, "session_id": "isolated-session", "tool_call_id": call,
        "function_name": tool, "status": status, "error_type": "TimeoutError",
        "error_message": "PRIVATE-BEARER-SECRET",
        "result": '{"password":"NEVER_COPY"}',
        "function_args": {"secret": "NEVER_COPY"},
    }


def _wait(ctx, minimum=1):
    for _ in range(300):
        history = ctx.state.values.get("retry_escalation_shadow_history", [])
        if len(history) >= minimum:
            return history
        time.sleep(0.01)
    raise AssertionError("retry observer did not write bounded telemetry")


def test_retry_default_off_and_success_does_not_probe(monkeypatch):
    plugin=load_plugin()
    calls=[]
    monkeypatch.setattr(plugin,"_safe_retry",lambda *args: calls.append(args))
    ctx=_ctx(False)
    plugin.register(ctx)
    assert ctx.hooks["post_tool_call"](**_failed()) is None
    assert calls==[]
    ctx=_ctx(True)
    plugin.register(ctx)
    kw=_failed()
    kw["status"]="success"
    assert ctx.hooks["post_tool_call"](**kw) is None
    assert calls==[]
    assert "last_retry_escalation_shadow" not in ctx.state.values


def test_retry_shadow_unknown_write_verify_no_raw_data(monkeypatch):
    plugin=load_plugin()
    payloads=[]
    def safe_retry(url, context, timeout, request_id):
        payloads.append(context)
        return {"retry":{
            "workflow":"retry_escalation_gate",
            "decision":"verify_state","guarded_decision":"verify_state",
            "raw_model_decision":None,"decision_source":"rule",
            "safety_override_reason":None,
            "reason":"unconfirmed_side_effect_verify_first",
            "backend":"rule","latency_ms":1.1,"confidence":1,
            "request_id":request_id,"advisory_only":True,
        },"error":None}
    monkeypatch.setattr(plugin,"_safe_retry",safe_retry)
    ctx=_ctx()
    plugin.register(ctx)
    assert ctx.hooks["post_tool_call"](**_failed()) is None
    history=_wait(ctx)
    assert len(payloads)==1
    assert payloads[0]["operation"]["side_effect_status"]=="unknown"
    assert payloads[0]["history"]["max_attempts"] is None
    assert payloads[0]["history"]["retry_budget_available"] is False
    assert history[0]["decision"]=="verify_state"
    assert history[0]["action_status"]=="observed"
    assert "PRIVATE" not in str(history)
    assert "NEVER_COPY" not in str(payloads)+str(history)


def test_retry_unsupported_tool_and_missing_id_never_infers_operation(monkeypatch):
    plugin=load_plugin()
    calls=[]
    monkeypatch.setattr(plugin,"_safe_retry",lambda *args: calls.append(args))
    ctx=_ctx()
    plugin.register(ctx)
    assert ctx.hooks["post_tool_call"](**_failed(tool="exec_command")) is None
    assert ctx.state.values["last_retry_escalation_shadow"]["action_status"]=="unsupported"
    no_id=_failed()
    no_id.pop("tool_call_id")
    assert ctx.hooks["post_tool_call"](**no_id) is None
    assert ctx.state.values["last_retry_escalation_shadow"]["action_reason"]=="tool_identity_unverified"
    assert calls==[]


def test_retry_deduplicates_and_cleans_on_session_boundary(monkeypatch):
    plugin=load_plugin()
    calls=[]
    def safe_retry(url, context, timeout, request_id):
        calls.append(request_id)
        return {"retry":None, "error":"down"}
    monkeypatch.setattr(plugin,"_safe_retry",safe_retry)
    ctx=_ctx()
    plugin.register(ctx)
    for ident in ("one","one","two","three"):
        ctx.hooks["post_tool_call"](**_failed(call=ident))
    history=_wait(ctx,2)
    assert len(calls)==2
    assert all(item["action_status"]=="failed_open" for item in history)
    ctx.hooks["on_session_end"](session_id="isolated-session",turn_id="turn-1")
    ctx.hooks["post_tool_call"](**_failed(call="one"))
    assert len(_wait(ctx,3))==3
    assert len(calls)==3


def test_retry_invalid_response_must_fail_open(monkeypatch):
    plugin=load_plugin()
    monkeypatch.setattr(plugin,"_post_json",lambda *args: {
        "workflow":"retry_escalation_gate","decision":"retry_same",
        "guarded_decision":"retry_same","advisory_only":False,
    })
    ctx=_ctx()
    plugin.register(ctx)
    assert ctx.hooks["post_tool_call"](**_failed()) is None
    assert _wait(ctx)[0]["action_status"]=="failed_open"
    assert _wait(ctx)[0]["action_reason"]=="retry_runtime_unavailable"


def test_retry_observer_saturation_drops_instead_of_blocking(monkeypatch):
    plugin=load_plugin()
    waiting=threading.Event()
    entered=threading.Event()
    lock=threading.Lock()
    count=[0]
    def slow(*args):
        with lock:
            count[0]+=1
            if count[0]==4: entered.set()
        waiting.wait(timeout=2)
        return {"retry":None,"error":"timeout"}
    monkeypatch.setattr(plugin,"_safe_retry", slow)
    ctx=_ctx()
    plugin.register(ctx)
    try:
        for i in range(4):
            ctx.hooks["post_tool_call"](**_failed(turn=f"parallel-{i}",call=str(i)))
        assert entered.wait(timeout=3)
        started=time.perf_counter()
        assert ctx.hooks["post_tool_call"](**_failed(turn="parallel-5",call="5")) is None
        assert time.perf_counter()-started<0.1
        assert ctx.state.values["last_retry_escalation_shadow"]["action_reason"]=="retry_capacity_exhausted"
    finally:
        waiting.set()
