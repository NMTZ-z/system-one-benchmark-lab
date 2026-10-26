"""Unit/forgery controls for separate read-only stock Shadow adjudicator."""
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase8_3_verify_stock_shadow as v


def fake_db(tmp_path):
    case=tmp_path / "off_stock_shell"
    case.mkdir()
    (case / "mutable/home/run").mkdir(parents=True)
    target=str(case / "mutable/home/run/missing.txt")
    db=case / "session-snapshot.db"
    with sqlite3.connect(db) as c:
        c.executescript("CREATE TABLE sessions(id,cwd,end_reason,tool_call_count,billing_base_url);"
                        "CREATE TABLE messages(id INTEGER PRIMARY KEY,timestamp,session_id,role,content,tool_call_id,tool_calls,tool_name);")
        c.execute("INSERT INTO sessions VALUES(?,?,?,?,?)",
                  ("sid",str(case/"mutable/home/run"),"agent_close",1,"http://127.0.0.1:1/v1"))
        tool=[{"id":"cid","function":{"name":"read_file","arguments":json.dumps({"path":target})}}]
        data=[("user",target,None,None,None),
              ("assistant",None,None,json.dumps(tool),None),
              ("tool",json.dumps({"not_found":True,"error":"File not found: " + target}),"cid",None,"read_file"),
              ("assistant","The requested file does not exist. No retry was attempted.",None,None,None)]
        for i,items in enumerate(data):
            c.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)",(i,i,"sid",*items))
    return case,target


def test_independent_native_sqlite_adjudicator_reads_original_fields(tmp_path):
    case,target=fake_db(tmp_path)
    sid,cid,sha,tool,status=v.native_case(case,target)
    assert (sid,cid,tool,status)==("sid","cid","read_file","tool_error_verified")
    assert sha==hashlib.sha256(b"The requested file does not exist. No retry was attempted.").hexdigest()


@pytest.mark.parametrize("mutation",[
    "fake_agent_success", "incorrect_call", "changed_path", "bad_tool_result",
    "wrong_route", "extra_session", "extra_final", "missing_tool_result",
])
def test_independent_native_oracle_rejects_forged_evidence(tmp_path,mutation):
    case,target=fake_db(tmp_path)
    with sqlite3.connect(case/"session-snapshot.db") as c:
        if mutation=="fake_agent_success":
            c.execute("UPDATE messages SET content='Task done' WHERE id=3")
        elif mutation=="incorrect_call":
            c.execute("UPDATE messages SET tool_call_id='wrong' WHERE role='tool'")
        elif mutation=="changed_path":
            target+='-forged'
        elif mutation=="bad_tool_result":
            c.execute("UPDATE messages SET content='{}' WHERE role='tool'")
        elif mutation=="wrong_route":
            c.execute("UPDATE sessions SET billing_base_url='https://real-provider.example'")
        elif mutation=="extra_session":
            c.execute("INSERT INTO sessions SELECT * FROM sessions")
        elif mutation=="extra_final":
            c.execute("INSERT INTO messages VALUES(4,4,'sid','assistant','extra',NULL,NULL,NULL)")
        elif mutation=="missing_tool_result":
            c.execute("DELETE FROM messages WHERE role='tool'")
    with pytest.raises(v.RequalificationBlocked):
        v.native_case(case,target)


def test_independent_hmac_has_unambiguous_scoped_truncation():
    key=bytes(range(32))
    reference=v.private_ref(key,"tool_call","sid\0cid")
    assert reference==hmac.new(key,b"tool_call\0sid\0cid",hashlib.sha256).hexdigest()[:32]
    assert reference!=v.private_ref(key,"session","sid\0cid")
    with pytest.raises(v.RequalificationBlocked): v.private_ref(b"bad","session","sid")
    with pytest.raises(v.RequalificationBlocked): v.private_ref(key,"session","")


def test_independent_snapshot_rejects_symlinked_private_bytes(tmp_path):
    protected=tmp_path/"protected.txt";protected.write_text("never read")
    root=tmp_path/"scratch";root.mkdir()
    (root/"linked").symlink_to(protected)
    with pytest.raises(v.RequalificationBlocked, match="bad_restored_object"):
        v.snapshot(root)


def test_independent_duplicate_and_missing_preregistration_block(tmp_path):
    with pytest.raises(v.RequalificationBlocked,match="missing_run_directory"):
        v.verify_matrix(tmp_path/"absent",tmp_path,tmp_path,tmp_path,"0"*40)
