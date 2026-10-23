"""H4B synthetic sqlite/read failure, not a real StepFun task."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from phase8_3_h4_failure_oracle import (
    check_sqlite_failed_read, manifest_target,NativeH4OracleBlocked,
    H4B_RUN_ID,
)


@pytest.fixture
def fake(tmp_path):
    folder=tmp_path/H4B_RUN_ID
    folder.mkdir(mode=0o700)
    target=folder/("h4b_absent_"+"5"*24+".txt")
    assert not target.exists()
    manifest={
        "scenario":"read_missing","path":str(target),
        "basename_sha256":hashlib.sha256(target.name.encode()).hexdigest(),
        "was_absent_before_agent":True,
    }
    p=folder/"h4b_missing_target.private.json"
    p.write_text(json.dumps(manifest))
    p.chmod(0o600)
    db=tmp_path/"native.db"
    with sqlite3.connect(db) as c:
        c.executescript(
            "CREATE TABLE sessions(id TEXT,cwd TEXT,tool_call_count INTEGER,"
            "billing_base_url TEXT,end_reason TEXT);"
            "CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id TEXT,"
            "role TEXT,content TEXT,tool_call_id TEXT,tool_calls TEXT,"
            "tool_name TEXT,timestamp INTEGER);")
        c.execute("INSERT INTO sessions VALUES (?,?,?,?,?)",
                  ("fake-session",str(folder.resolve()),1,
                   "http://127.0.0.1:18794","agent_close"))
        call=json.dumps([{
            "id":"fake-call","function":{
                "name":"read_file","arguments":json.dumps({"path":str(target)}),
            }
        }])
        response=json.dumps({
            "not_found":True,"content":"","error":"File not found: "+str(target),
        })
        rows=[
            ("user","Please read "+str(target),None,None,None,1),
            ("assistant",None,None,call,None,2),
            ("tool",response,"fake-call",None,"read_file",3),
            ("assistant","Original file could not be found.",None,None,None,4),
        ]
        c.executemany(
            "INSERT INTO messages(session_id,role,content,tool_call_id,tool_calls,tool_name,timestamp)"
            "VALUES ('fake-session',?,?,?,?,?,?)",rows,
        )
    return db,folder,target


def test_new_h4b_native_file_oracle_true_failure_only(fake):
    db,folder,target=fake
    assert manifest_target(folder,expected_case=H4B_RUN_ID)==target
    result=check_sqlite_failed_read(db,folder,expected_case=H4B_RUN_ID)
    assert result["native_result_structured_missing_file"] is True
    assert result["tool_calls_exactly_one"] is True
    assert result["target_absent_before_and_after"] is True
    assert result["native_failure_status_propagated_to_retry_hook"]=="NOT_ESTABLISHED"
    assert not target.exists()


def test_new_h4b_does_not_override_old_h4_native_case_identity(fake):
    db,folder,target=fake
    with pytest.raises(NativeH4OracleBlocked):
        check_sqlite_failed_read(db,folder)
    with pytest.raises(NativeH4OracleBlocked):
        manifest_target(folder,expected_case="h4_missing_read")
    with pytest.raises(NativeH4OracleBlocked):
        manifest_target(folder,expected_case="unknown")


def test_fabricated_success_message_or_wrong_target_fails(fake):
    db,folder,target=fake
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE messages SET content=? WHERE role='tool'",
                     (json.dumps({"content":"falsified","not_found":False}),))
    with pytest.raises(NativeH4OracleBlocked):
        check_sqlite_failed_read(db,folder,expected_case=H4B_RUN_ID)
    target.write_text("unexpected success artifact")
    with pytest.raises(NativeH4OracleBlocked):
        manifest_target(folder,expected_case=H4B_RUN_ID)


def test_H4C_missing_file_oracle_requires_new_distinct_original(tmp_path):
    from phase8_3_h4_failure_oracle import (
        manifest_target, NativeH4OracleBlocked, H4C_RUN_ID,
    )
    case=tmp_path/H4C_RUN_ID
    case.mkdir(mode=0o700)
    absent=case/("h4c_absent_"+"c"*24+".txt")
    manifest={
        "scenario":"read_missing","path":str(absent),
        "basename_sha256":hashlib.sha256(absent.name.encode()).hexdigest(),
        "was_absent_before_agent":True,
    }
    name=case/"h4c_missing_target.private.json"
    name.write_text(json.dumps(manifest))
    name.chmod(0o600)
    assert manifest_target(case,expected_case=H4C_RUN_ID)==absent
    assert absent.exists() is False
    with pytest.raises(NativeH4OracleBlocked):
        manifest_target(case,expected_case="h4b_missing_read")
    manifest["path"]=str(tmp_path/"outside.txt")
    name.write_text(json.dumps(manifest))
    with pytest.raises(NativeH4OracleBlocked):
        manifest_target(case,expected_case=H4C_RUN_ID)
