"""Native Hermes *failed* read oracle tests. Purely synthetic SQLite fixtures."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from phase8_3_h4_failure_oracle import (
    check_sqlite_failed_read, manifest_target, NativeH4OracleBlocked,
)

@pytest.fixture()
def fixture(tmp_path):
    run = tmp_path / "h4_missing_read"
    run.mkdir(mode=0o700)
    missing = run / ("h4_absent_" + "a" * 24 + ".txt")
    assert not missing.exists()
    manifest = {
        "scenario": "read_missing", "path": str(missing),
        "basename_sha256": hashlib.sha256(missing.name.encode()).hexdigest(),
        "was_absent_before_agent": True,
    }
    (run / "h4_missing_target.private.json").write_text(json.dumps(manifest))
    db_path = tmp_path / "isolated.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            "CREATE TABLE sessions("
            "id TEXT, cwd TEXT, tool_call_count INTEGER, "
            "billing_base_url TEXT, end_reason TEXT);"
            "CREATE TABLE messages("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "session_id TEXT, role TEXT, content TEXT,"
            "tool_call_id TEXT, tool_calls TEXT,"
            "tool_name TEXT, timestamp REAL);"
        )
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (
            "SYNTHETIC_H4_SESSION_ID",str(run.resolve()),1,
            "http://127.0.0.1:18794","agent_close",
        ))
        call = json.dumps([{
            "id":"SYNTHETIC_TOOL_CALL_ID",
            "type":"function",
            "function":{"name":"read_file",
                        "arguments":json.dumps({"path":str(missing)})},
        }])
        result = json.dumps({
            "content": "", "error": "File not found: " + str(missing),
            "not_found": True, "file_size": 0,
        })
        rows=[
            ("user",f"Read only the file {missing}; report if absent.",None,None,None,1),
            ("assistant",None,None,call,None,2),
            ("tool",result,"SYNTHETIC_TOOL_CALL_ID",None,"read_file",3),
            ("assistant","The file does not exist. No changes made.",None,None,None,4),
        ]
        db.executemany(
            "INSERT INTO messages(session_id,role,content,tool_call_id,tool_calls,tool_name,timestamp)"
            " VALUES ('SYNTHETIC_H4_SESSION_ID',?,?,?,?,?,?)",rows
        )
    return db_path,run,missing


def tweak_db(db: Path, statement: str, bindings=()):
    with sqlite3.connect(db) as conn:
        conn.execute(statement, bindings)


def test_h4_structured_missing_file_oracle_passes_only_with_native_evidence(fixture):
    db,run,missing=fixture
    outcome=check_sqlite_failed_read(db,run)
    assert outcome["native_result_structured_missing_file"] is True
    assert outcome["tool_call_result_identity_paired"] is True
    assert outcome["target_absent_before_and_after"] is True
    assert outcome["tool_calls_exactly_one"] is True
    assert outcome["retry_gate_model_invoked"]=="NOT_ESTABLISHED"
    assert outcome["native_failure_status_propagated_to_retry_hook"]=="NOT_ESTABLISHED"
    assert outcome["agent_final_semantically_truthful"]=="NOT_AUTOMATICALLY_VERIFIED"
    assert not missing.exists()
    text=json.dumps(outcome)
    assert str(missing) not in text
    assert "SYNTHETIC_H4_SESSION_ID" not in text
    assert "SYNTHETIC_TOOL_CALL_ID" not in text


@pytest.mark.parametrize("mutation",[
    "target_created","target_symlink","manifest_path",
    "wrong_tool","tool_call_wrong_path",
    "tool_result_not_error","error_success_mix",
    "tool_result_wrong_id","extra_tool_message",
    "wrong_provider","agent_not_closed","no_final",
])
def test_h4_falsified_native_negative_evidence_cannot_pass(fixture,mutation):
    db,run,missing=fixture
    if mutation=="target_created":
        missing.write_text("not a missing file")
    elif mutation=="target_symlink":
        missing.symlink_to(run / "does_not_exist")
    elif mutation=="manifest_path":
        p=run/"h4_missing_target.private.json"
        j=json.loads(p.read_text())
        j["path"]=str(run/"outside")
        p.write_text(json.dumps(j))
    elif mutation=="wrong_tool":
        tweak_db(db,"UPDATE messages SET tool_name='write_file' WHERE role='tool'")
    elif mutation=="tool_call_wrong_path":
        tweak_db(db,"UPDATE messages SET tool_calls=? WHERE tool_calls IS NOT NULL",
                 (json.dumps([{"id":"SYNTHETIC_TOOL_CALL_ID",
                     "function":{"name":"read_file",
                                 "arguments":json.dumps({"path":"/tmp/different"})}}]),))
    elif mutation=="tool_result_not_error":
        tweak_db(db,"UPDATE messages SET content=? WHERE role='tool'",
                 (json.dumps({"content":"some content","not_found":False}),))
    elif mutation=="error_success_mix":
        tweak_db(db,"UPDATE messages SET content=? WHERE role='tool'",
                 (json.dumps({"content":"fake successful bytes",
                             "error":"File not found: mock", "not_found":True}),))
    elif mutation=="tool_result_wrong_id":
        tweak_db(db,"UPDATE messages SET tool_call_id='different' WHERE role='tool'")
    elif mutation=="extra_tool_message":
        tweak_db(db,"INSERT INTO messages(session_id,role,content,tool_call_id,tool_name,timestamp)"
                 " VALUES ('SYNTHETIC_H4_SESSION_ID','tool','error','other','read_file',8)")
    elif mutation=="wrong_provider":
        tweak_db(db,"UPDATE sessions SET billing_base_url='https://api.stepfun.com/v1'")
    elif mutation=="agent_not_closed":
        tweak_db(db,"UPDATE sessions SET end_reason='interrupted'")
    elif mutation=="no_final":
        tweak_db(db,"UPDATE messages SET content=NULL WHERE role='assistant' AND tool_calls IS NULL")
    with pytest.raises(NativeH4OracleBlocked):
        check_sqlite_failed_read(db,run)


def test_h4_native_tool_error_is_not_same_as_authoritative_hook_status():
    import importlib.util
    path=ROOT/"integrations/hermes/local-system-one-hermes/__init__.py"
    spec=importlib.util.spec_from_file_location("h4_retry_test_plugin",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # JSON tool-error string alone is NOT typed status; cannot infer Retry Gate.
    assert mod._retry_failure({
        "tool_name":"read_file",
        "result":json.dumps({"error":"File not found: synthetic"}),
    }) is None
    fail=mod._retry_failure({
        "tool_name":"read_file","status":"failed",
        "error_type":"FileNotFoundError",
    })
    assert fail is not None
    assert fail["category"]=="tool_error"
    assert fail["transience"]=="unknown"
    ctx=mod._retry_context({
        "tool_name":"read_file","status":"failed",
        "error_type":"FileNotFoundError",
    })
    assert ctx["history"]["retry_budget_available"] is False
    assert ctx["operation"]["side_effect"]=="none"
