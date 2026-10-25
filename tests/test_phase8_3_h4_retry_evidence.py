"""Synthetic native SQLite/HMAC Retry cross-layer joins, no Agent/Provider."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from phase8_3_h4_retry_evidence import verify_retry_exact, RetryEvidenceBlocked
from phase8_2b_native_correlate import ref

KEY = b"\x74"*32
SESSION = "SYNTHETIC_H4_SESSION"
TOOL = "SYNTHETIC_H4_TOOL"
REQUEST = "SYNTHETIC_H4_ADVISORY_REQUEST"


@pytest.fixture()
def bundle(tmp_path):
    run=tmp_path/"h4_missing_read"
    run.mkdir()
    db=tmp_path/"native.db"
    with sqlite3.connect(db) as handle:
        handle.executescript("CREATE TABLE sessions(id TEXT,cwd TEXT);"
                             "CREATE TABLE messages(session_id TEXT,role TEXT,tool_call_id TEXT);")
        handle.execute("INSERT INTO sessions VALUES (?,?)",(SESSION,str(run.resolve())))
        handle.execute("INSERT INTO messages VALUES (?,?,?)",(SESSION,"tool",TOOL))
    sessionref=ref(KEY,"session",SESSION)
    toolref=ref(KEY,"tool_call",SESSION+"\x00"+TOOL)
    turnref=ref(KEY,"turn",SESSION+"\x00"+"synthetic-turn")
    requested=ref(KEY,"decision_request",REQUEST)
    completion=[
        {"gate":"completion","native_stage":"tool_result",
         "session_ref":sessionref,"tool_call_ref":toolref,"turn_ref":turnref},
        {"gate":"completion","native_stage":"turn_end",
         "session_ref":sessionref,"turn_ref":turnref},
    ]
    retry=[{
        "gate":"retry_escalation","mode":"shadow","native_stage":"tool_result",
        "session_ref":sessionref,"tool_call_ref":toolref,"turn_ref":turnref,
        "request_id":REQUEST,"decision_request_ref":requested,
        "response_request_id_matches":True,
        "action_status":"observed","action_reason":"retry_shadow_advisory_only",
        "decision":"ask_user",
    }]
    http=[
        {"path":"/v1/workflows/completion-gate","http_status":200,"backend":"mlx"},
        {"path":"/v1/workflows/completion-gate","http_status":200,"backend":"mlx"},
        {"path":"/v1/workflows/retry-escalation-gate","http_status":200,
         "workflow":"retry_escalation_gate",
         "decision_request_ref":requested,
         "response_matches_request_id":True,
         "backend":"mlx","decision_source":"model"},
    ]
    return db,run,retry,completion,http


def test_strict_h4_retry_hmac_and_native_failure_event_join(bundle):
    db,run,retry,completion,http=bundle
    got=verify_retry_exact(db,run,KEY,retry_adapter=retry,
                           completion_adapter=completion,http=http)
    assert got["native_retry_tool_hmac_match"]
    assert got["native_completion_same_tool_hmac_match"]
    assert got["retry_http_hmac_exact_match"]
    assert got["no_native_retry_or_active_action_observed_from_advisor"]
    assert got["retry_decision_observed"]=="ask_user"
    assert SESSION not in str(got) and TOOL not in str(got) and REQUEST not in str(got)


@pytest.mark.parametrize("mutation",[
    "native_tool_id","retry_tool_ref","retry_session","retry_turn",
    "retry_request_id","duplicate_retry","missing_retry","completion_missing",
    "duplicate_completion","http_unmatched","http_502","http_no_echo",
    "http_wrong_workflow","retry_no_echo","retry_not_observed",
    "retry_action","retry_bad_decision","cross_session_id",
])
def test_untrusted_h4_retry_lineage_refuses_to_pass(bundle,mutation):
    db,run,retry,completion,http=bundle
    if mutation=="native_tool_id":
        with sqlite3.connect(db) as x:
            x.execute("UPDATE messages SET tool_call_id='wrong'")
    elif mutation=="cross_session_id":
        with sqlite3.connect(db) as x:
            x.execute("UPDATE sessions SET id='different'")
    elif mutation=="retry_tool_ref":retry[0]["tool_call_ref"]="0"*32
    elif mutation=="retry_session":retry[0]["session_ref"]="0"*32
    elif mutation=="retry_turn":retry[0]["turn_ref"]="0"*32
    elif mutation=="retry_request_id":retry[0]["request_id"]="forged"
    elif mutation=="duplicate_retry":retry.append(deepcopy(retry[0]))
    elif mutation=="missing_retry":retry.clear()
    elif mutation=="completion_missing":completion.pop(0)
    elif mutation=="duplicate_completion":completion.append(deepcopy(completion[0]))
    elif mutation=="http_unmatched":http[2]["decision_request_ref"]="0"*32
    elif mutation=="http_502":http[2]["http_status"]=502
    elif mutation=="http_no_echo":http[2]["response_matches_request_id"]=None
    elif mutation=="http_wrong_workflow":http[2]["workflow"]="completion_gate"
    elif mutation=="retry_no_echo":retry[0]["response_request_id_matches"]=False
    elif mutation=="retry_not_observed":retry[0]["action_status"]="failed_open"
    elif mutation=="retry_action":retry[0]["action_reason"]="active_retry_applied"
    elif mutation=="retry_bad_decision":retry[0]["decision"]="force_retry"
    with pytest.raises(RetryEvidenceBlocked):
        verify_retry_exact(db,run,KEY,retry_adapter=retry,
                           completion_adapter=completion,http=http)
