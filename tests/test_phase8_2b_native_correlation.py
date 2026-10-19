"""8.2B private-to-public evidence join tests, no API, model or production Agent."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2b_native_correlate import correlate, ref, CorrelationError

KEY = b"\x7e" * 32
SID = "SYNTHETIC_NATIVE_SESSION_NOT_TO_EXPORT"
CALL = "SYNTHETIC_NATIVE_CALL_NOT_TO_EXPORT"
RID = "SYNTHETIC_RANDOM_REQUEST_NOT_TO_EXPORT"


def _sdk_frames():
    def frame(name, data):
        return {"method": "session.event", "params": {
            "sessionId": SID, "event": {"type": name, "data": data},
        }}
    return [
        frame("turn/start", {"turn": 1}),
        frame("tool/call", {"turn": 1, "callId": CALL, "name": "read"}),
        frame("tool/result", {"turn": 1, "message": {"source": {"callId": CALL}, "isError": False}}),
        frame("turn/end", {"turn": 1, "reason": {"kind": "completed"}}),
    ]


def _adapter(stage="tool_result", rid=RID, call=CALL):
    inner = SID + "\x00" + "1" + "\x00" + stage
    if stage == "tool_result":
        inner += "\x00" + call
    return {
        "platform": "deepseek_harness",
        "gate": "completion", "request_id": rid, "native_stage": stage,
        "session_ref": ref(KEY, "session", SID),
        "turn_ref": ref(KEY, "turn", SID + "\x00" + "1"),
        "native_event_ref": ref(KEY, "native_event", inner),
        "decision_request_ref": ref(KEY, "decision_request", rid),
        "action_status": "observed",
    }


def _proxy(rid=RID, status=200, matches=True):
    return {
        "decision_request_ref": ref(KEY, "decision_request", rid),
        "http_status": status, "response_matches_request_id": matches,
    }


def test_real_native_sdk_frame_shape_correlates_exact_id_across_layers():
    adapter = [_adapter(), _adapter("turn_end", "request-end")]
    proxy = [_proxy(), _proxy("request-end")]
    result = correlate("deepseek_harness", _sdk_frames(), adapter, proxy, KEY)
    assert result["status"] == "PASS"
    assert result["native_http_pairs_verified"] == 2
    assert result["task_outcome"] == result["agent_execution_outcome"] == "UNKNOWN"
    raw = json.dumps(result)
    for private in (SID, CALL, RID):
        assert private not in raw


def test_runtime_down_request_join_still_verifies_without_forged_response():
    x = correlate("deepseek_harness", _sdk_frames(), [_adapter()],
                  [_proxy(status=503, matches=None)], KEY)
    assert x["status"] == "PASS"
    assert x["pairs"][0]["http_status"] == 503


@pytest.mark.parametrize("mutation,expect", [
    ("native_call", "PARTIAL"),
    ("turn_id", "BLOCKED"),
    ("proxy_request", "BLOCKED"),
    ("proxy_collision", "BLOCKED"),
    ("response_mismatch", "BLOCKED"),
    ("duplicate_adapter", "BLOCKED"),
])
def test_conflicts_missing_or_conflicting_links_never_pass(mutation, expect):
    native, adapter, proxy = _sdk_frames(), [_adapter()], [_proxy()]
    if mutation == "native_call":
        native[2]["params"]["event"]["data"]["message"]["source"]["callId"] = "other"
    elif mutation == "turn_id":
        adapter[0]["turn_ref"] = ref(KEY, "turn", SID + "\x00" + "2")
    elif mutation == "proxy_request":
        proxy[0]["decision_request_ref"] = ref(KEY, "decision_request", "other")
    elif mutation == "proxy_collision":
        proxy.append(deepcopy(proxy[0]))
    elif mutation == "response_mismatch":
        proxy[0]["response_matches_request_id"] = False
    elif mutation == "duplicate_adapter":
        adapter.append(deepcopy(adapter[0]))
    result = correlate("deepseek_harness", native, adapter, proxy, KEY)
    assert result["status"] == expect


def test_missing_native_provenance_not_made_up_from_time_window():
    native = [{"method": "session.event", "params": {
        "sessionId": SID, "event": {"type": "turn/end", "data": {"turn": 999}},
    }}]
    r = correlate("deepseek_harness", native, [_adapter()], [_proxy()], KEY)
    assert r["status"] == "PARTIAL"
    assert r["native_http_pairs_verified"] == 0


@pytest.mark.parametrize("mutation,expected_issue", [
    ("missing_native_call", "unpaired_native_tool_result"),
    ("duplicate_native_call", "duplicate_native_tool_call"),
    ("missing_native_start", "native_turn_start_missing"),
    ("cross_session_native_call", "unpaired_native_tool_result"),
])
def test_native_sdk_tool_and_turn_lifecycle_not_assumed(mutation, expected_issue):
    native = _sdk_frames()
    if mutation == "missing_native_call":
        native.pop(1)
    elif mutation == "duplicate_native_call":
        native.insert(2, deepcopy(native[1]))
    elif mutation == "missing_native_start":
        native.pop(0)
    elif mutation == "cross_session_native_call":
        native[1]["params"]["sessionId"] = "other_private_session"
    outcome = correlate("deepseek_harness", native, [_adapter()], [_proxy()], KEY)
    assert outcome["status"] != "PASS"
    assert expected_issue in outcome["issues"]


def _make_sqlite(tmp_path: Path, *, user_turns=1) -> Path:
    db_path = tmp_path / "isolated.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            "CREATE TABLE sessions(id TEXT,end_reason TEXT);"
            "CREATE TABLE messages(session_id TEXT,role TEXT,tool_call_id TEXT);"
        )
        db.execute("INSERT INTO sessions VALUES (?,?)", (SID, "agent_close"))
        for _ in range(user_turns):
            db.execute("INSERT INTO messages VALUES (?,?,?)", (SID, "user", None))
        db.execute("INSERT INTO messages VALUES (?,?,?)", (SID, "tool", CALL))
    return db_path


def _hermes_adapter(stage: str) -> dict:
    base = {"gate": "completion", "native_stage": stage,
            "session_ref": ref(KEY, "session", SID),
            "decision_request_ref": ref(KEY, "decision_request", RID)}
    if stage == "tool_result":
        base["tool_call_ref"] = ref(KEY, "tool_call", SID + "\x00" + CALL)
    return base


def test_hermes_native_sqlite_tool_call_exact_join(tmp_path):
    p = _make_sqlite(tmp_path)
    result = correlate("hermes", p, [_hermes_adapter("tool_result")], [_proxy()], KEY)
    assert result["status"] == "PASS"
    assert result["native_http_pairs_verified"] == 1


def test_hermes_multiturn_sqlite_does_not_authenticate_ambiguous_end(tmp_path):
    p = _make_sqlite(tmp_path, user_turns=2)
    result = correlate("hermes", p, [_hermes_adapter("turn_end")], [_proxy()], KEY)
    assert result["status"] == "PARTIAL"
    assert "hermes_session_turn_identity_ambiguous" in result["issues"]


def test_no_export_of_private_data_or_outbound_requests(tmp_path):
    with pytest.raises(CorrelationError):
        ref(KEY, "unsupported", SID)
    with pytest.raises(CorrelationError):
        correlate("jev-any", [], [], [], KEY)


def _hermes_plugin():
    import importlib.util
    filename = (Path(__file__).resolve().parents[1] /
                "integrations/hermes/local-system-one-hermes/__init__.py")
    spec = importlib.util.spec_from_file_location("isolated_hermes_evidence", filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_actual_hermes_plugin_generates_same_scoped_session_and_tool_refs(monkeypatch):
    module = _hermes_plugin()
    kwargs = {"session_id": SID, "turn_id": "T1", "tool_call_id": CALL}
    assert module._private_evidence_refs(kwargs, RID, "tool_result") == {}
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE", "isolated-shadow-test-v1")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX", KEY.hex())
    produced = module._private_evidence_refs(kwargs, RID, "tool_result")
    assert produced["session_ref"] == ref(KEY, "session", SID)
    assert produced["tool_call_ref"] == ref(KEY, "tool_call", SID + "\x00" + CALL)
    assert produced["decision_request_ref"] == ref(KEY, "decision_request", RID)
    assert produced["turn_ref"] == ref(KEY, "turn", SID + "\x00T1")
    assert SID not in json.dumps(produced)
    assert RID not in json.dumps(produced)
    assert module._private_evidence_refs(
        {"session_id": SID, "tool_call_id": CALL}, RID, "tool_result"
    ).get("turn_ref") is None


def test_hermes_invalid_or_missing_native_ids_are_not_fabricated(monkeypatch):
    module = _hermes_plugin()
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE", "isolated-shadow-test-v1")
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX", KEY.hex())
    assert module._private_evidence_refs({"turn_id": "T1"}, RID, "turn_end") == {}
    assert module._private_evidence_refs({"session_id": SID}, "", "turn_end") == {}
    monkeypatch.setenv("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX", "BAD")
    assert module._private_evidence_refs({"session_id": SID}, RID, "turn_end") == {}
