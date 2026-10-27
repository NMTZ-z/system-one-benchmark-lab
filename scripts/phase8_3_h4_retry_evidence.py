#!/usr/bin/env python3
"""H4 private native Retry Shadow exact tool/Adapter/HTTP HMAC correlation.

The Retry advisor may observe a native FAILED read_file, but it must NEVER
take an action. HMAC request reference alone is insufficient: recompute
from the one authentic Hermes SQLite Session/Tool call, check its matching
Completion loop-tool observation and one corresponding HTTP response.
No Provider I/O, task retries, credentials, tool outputs or raw IDs emitted.
"""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any

from phase8_2b_native_correlate import ref

ALLOWED_DECISIONS = frozenset({
    "retry_same","try_alternative","escalate_model",
    "verify_state","ask_user","abort",
})


class RetryEvidenceBlocked(ValueError):
    pass


def verify_retry_exact(
    db_path: Path, run_directory: Path,
    key: bytes, *,
    retry_adapter: list[dict[str, Any]],
    completion_adapter: list[dict[str, Any]],
    http: list[dict[str, Any]],
    expected_case: str="h4_missing_read",
) -> dict[str, Any]:
    if (not isinstance(key,bytes) or len(key)!=32 or
            db_path.is_symlink() or not db_path.is_file()
            or not run_directory.is_dir() or run_directory.is_symlink()
            or expected_case not in {"h4_missing_read","h4b_missing_read","h4c_missing_read","h4d_missing_read","h4e_missing_read"}
            or run_directory.name!=expected_case):
        raise RetryEvidenceBlocked("not the isolated H4/H4B native source and evidence key")
    if not isinstance(retry_adapter,list) or len(retry_adapter)!=1:
        raise RetryEvidenceBlocked("exactly one H4 Retry observation required")
    if not isinstance(completion_adapter,list) or len(completion_adapter)!=2:
        raise RetryEvidenceBlocked("exactly two H4 Completion observations required")
    if not isinstance(http,list) or len(http)!=3:
        raise RetryEvidenceBlocked("expected two Completion + one Retry actual HTTP events")
    uri=f"file:{db_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri,uri=True,timeout=4) as db:
        rows=db.execute("SELECT id FROM sessions WHERE cwd=?",
                        (str(run_directory.resolve()),)).fetchall()
        if len(rows)!=1:
            raise RetryEvidenceBlocked("H4 native Session cannot be uniquely identified")
        sid=rows[0][0]
        tools=db.execute(
            "SELECT tool_call_id FROM messages WHERE session_id=? AND role='tool'",
            (sid,),
        ).fetchall()
        if len(tools)!=1 or not isinstance(tools[0][0],str):
            raise RetryEvidenceBlocked("H4 native tool result ID ambiguous")
        call=tools[0][0]
    session_ref=ref(key,"session",sid)
    tool_ref=ref(key,"tool_call",sid+"\x00"+call)
    retry=retry_adapter[0]
    completion_tool=[
        row for row in completion_adapter if row.get("native_stage")=="tool_result"
    ]
    if len(completion_tool)!=1:
        raise RetryEvidenceBlocked("original native tool-result completion identity missing")
    c=completion_tool[0]
    if (retry.get("gate")!="retry_escalation" or
            retry.get("mode")!="shadow" or
            retry.get("native_stage")!="tool_result" or
            retry.get("session_ref")!=session_ref or
            retry.get("tool_call_ref")!=tool_ref or
            retry.get("turn_ref")!=c.get("turn_ref") or
            not isinstance(retry.get("turn_ref"),str) or
            len(retry["turn_ref"])!=32 or
            c.get("session_ref")!=session_ref or
            c.get("tool_call_ref")!=tool_ref):
        raise RetryEvidenceBlocked("Retry is not keyed to the exact native failed read")
    retry_id=retry.get("request_id")
    if (not isinstance(retry_id,str) or not retry_id
            or retry.get("decision_request_ref")!=ref(key,"decision_request",retry_id)):
        raise RetryEvidenceBlocked("Retry decision request HMAC mismatched")
    matches=[
        row for row in http if row.get("path")=="/v1/workflows/retry-escalation-gate"
    ]
    if len(matches)!=1 or matches[0].get("decision_request_ref")!=retry["decision_request_ref"]:
        raise RetryEvidenceBlocked("Retry HMAC request not uniquely paired with real HTTP")
    remote=matches[0]
    if (remote.get("http_status")!=200 or remote.get("workflow")!="retry_escalation_gate"
            or remote.get("response_matches_request_id") is not True
            or retry.get("response_request_id_matches") is not True
            or remote.get("backend") not in {"mlx","rule"}
            or remote.get("decision_source") not in {"model","rule"}
            or retry.get("action_status")!="observed"
            or retry.get("action_reason")!="retry_shadow_advisory_only"
            or retry.get("decision") not in ALLOWED_DECISIONS):
        raise RetryEvidenceBlocked("no bounded real local Retry advisory evidence")
    return {
        "schema":"local-system-one/phase8_3-h4-retry-native-request-join-v1",
        "native_real_missing_file_tool_ref_proven":True,
        "adapter_retry_shadow_record_count":1,
        "native_retry_tool_hmac_match":True,
        "native_completion_same_tool_hmac_match":True,
        "native_turn_hmac_shared_with_completion":True,
        "retry_http_hmac_exact_match":True,
        "retry_http_status":200,
        "runtime_backend":remote.get("backend"),
        "retry_decision_observed":retry["decision"],
        "no_native_retry_or_active_action_observed_from_advisor":True,
        "raw_identifiers_exported":False,
        "active_authority":"NOT_AUTHORIZED",
    }
