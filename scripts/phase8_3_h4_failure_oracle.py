#!/usr/bin/env python3
"""Independent H4 native missing-file tool failure oracle, NO main Provider calls.

Only honors a PRE-AGENT private manifest in the exact H4 disposable run folder.
Requires a genuinely missing file, exactly one matched native read_file call
and Hermes' typed result JSON (not text claimed by the model). Does not
assert Retry Gate eligibility from a JSON error alone: the Hermes plugin
requires a separate trustworthy native post_tool_call failure STATUS.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from typing import Any

RUN_ID = "h4_missing_read"
H4B_RUN_ID = "h4b_missing_read"
H4C_RUN_ID = "h4c_missing_read"
H4D_RUN_ID = "h4d_missing_read"
PATTERN = re.compile(r"h4_absent_[a-f0-9]{24}\.txt\Z")
H4B_PATTERN = re.compile(r"h4b_absent_[a-f0-9]{24}\.txt\Z")
H4C_PATTERN = re.compile(r"h4c_absent_[a-f0-9]{24}\.txt\Z")
H4D_PATTERN = re.compile(r"h4d_absent_[a-f0-9]{24}\.txt\Z")
FAILURE_PREFIX = "File not found:"


class NativeH4OracleBlocked(ValueError):
    """Expected missing-file tool failure cannot be independently verified."""


def manifest_target(
    run_dir: Path, *, expected_case: str=RUN_ID,
) -> Path:
    if expected_case not in {RUN_ID,H4B_RUN_ID,H4C_RUN_ID,H4D_RUN_ID}:
        raise NativeH4OracleBlocked("only frozen H4/H4B/H4C cases permitted")
    if run_dir.is_symlink() or not run_dir.is_dir() or run_dir.name != expected_case:
        raise NativeH4OracleBlocked("missing-read must be isolated H4 or H4B")
    manifest_name=(
        "h4_missing_target.private.json" if expected_case==RUN_ID
        else "h4b_missing_target.private.json" if expected_case==H4B_RUN_ID
        else "h4c_missing_target.private.json" if expected_case==H4C_RUN_ID
        else "h4d_missing_target.private.json"
    )
    manifest = run_dir / manifest_name
    if manifest.is_symlink() or not manifest.is_file():
        raise NativeH4OracleBlocked("missing original private H4 target manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {
        "scenario", "path", "basename_sha256", "was_absent_before_agent"
    }:
        raise NativeH4OracleBlocked("untrusted original H4 manifest schema")
    import hashlib
    target = Path(data["path"]) if isinstance(data["path"], str) else Path(".")
    if (data["scenario"] != "read_missing"
            or data["was_absent_before_agent"] is not True
            or not target.is_absolute()
            or target.parent != run_dir.absolute()
            or not ({RUN_ID:PATTERN,H4B_RUN_ID:H4B_PATTERN,
                     H4C_RUN_ID:H4C_PATTERN,H4D_RUN_ID:H4D_PATTERN}[expected_case]).fullmatch(target.name)
            or data["basename_sha256"] != hashlib.sha256(
                target.name.encode("utf-8")).hexdigest()):
        raise NativeH4OracleBlocked("negative target is not the preregistered H4 file")
    if target.exists() or target.is_symlink():
        raise NativeH4OracleBlocked("expected missing-file target exists after native task")
    if (run_dir / "output.txt").exists() or (run_dir / "output.txt").is_symlink():
        raise NativeH4OracleBlocked("H4 must not create a success artifact")
    return target


def check_sqlite_failed_read(
    db_path: Path, run_dir: Path, *, expected_case: str=RUN_ID,
) -> dict[str, Any]:
    """Validate genuine native tool/error/result identity, no heuristic Agent text.

    SQLite database is only opened read-only. No user-supplied Session IDs,
    raw tool results, argument values or original target paths are returned.
    """
    target = manifest_target(run_dir,expected_case=expected_case)
    if db_path.is_symlink() or not db_path.is_file():
        raise NativeH4OracleBlocked("native Hermes test SQLite unavailable")
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=4) as db:
        db.row_factory = sqlite3.Row
        sessions = db.execute(
            "SELECT id, cwd, tool_call_count, billing_base_url, end_reason "
            "FROM sessions WHERE cwd=?", (str(run_dir.resolve()),)
        ).fetchall()
        if len(sessions) != 1:
            raise NativeH4OracleBlocked("one native H4 Hermes session required")
        sess = sessions[0]
        if (sess["tool_call_count"] != 1
                or sess["billing_base_url"] != "http://127.0.0.1:18794"
                or sess["end_reason"] != "agent_close"):
            raise NativeH4OracleBlocked("H4 original native tool/provider/closure mismatch")
        rows = db.execute(
            "SELECT role, content, tool_call_id, tool_calls, tool_name "
            "FROM messages WHERE session_id=? ORDER BY timestamp, id",
            (sess["id"],)
        ).fetchall()
    if len(rows) != 4 or [r["role"] for r in rows] != [
        "user", "assistant", "tool", "assistant"
    ]:
        raise NativeH4OracleBlocked("unexpected extra/unpaired tool or Agent message")
    user, request, returned, final = rows
    prompt = str(user["content"] or "")
    if (str(target) not in prompt
            or not isinstance(request["tool_calls"], str)
            or final["tool_calls"]
            or not isinstance(final["content"], str)
            or not final["content"].strip()):
        raise NativeH4OracleBlocked("native task prompt/turn structure mismatched")
    calls = json.loads(request["tool_calls"])
    if not isinstance(calls, list) or len(calls) != 1:
        raise NativeH4OracleBlocked("native H4 did not make exactly one tool call")
    call = calls[0]
    fn = call.get("function") if isinstance(call, dict) else None
    if not isinstance(fn, dict) or fn.get("name") != "read_file":
        raise NativeH4OracleBlocked("native H4 called an unapproved tool")
    args = json.loads(fn.get("arguments", "")) if isinstance(
        fn.get("arguments"), str) else fn.get("arguments")
    if (not isinstance(args, dict)
            or args.get("path") != str(target)
            or set(args) - {"path", "offset", "limit"}):
        raise NativeH4OracleBlocked("native H4 model changed the missing file path")
    if (returned["tool_name"] != "read_file"
            or not isinstance(call.get("id"), str)
            or not call["id"]
            or returned["tool_call_id"] != call["id"]):
        raise NativeH4OracleBlocked("native H4 tool call/result IDs do not pair")
    parsed = json.loads(returned["content"]) if isinstance(
        returned["content"], str) else None
    if (not isinstance(parsed, dict)
            or parsed.get("not_found") is not True
            or not isinstance(parsed.get("error"), str)
            or not parsed["error"].startswith(FAILURE_PREFIX)
            or bool(parsed.get("content"))):
        raise NativeH4OracleBlocked("native tool did not actually return missing-file failure")
    # Recheck filesystem after reading real native SQLite evidence.
    manifest_target(run_dir,expected_case=expected_case)
    return {
        "native_session_unique": True,
        "tool_calls_exactly_one": True,
        "native_tool": "read_file",
        "tool_call_result_identity_paired": True,
        "native_result_structured_missing_file": True,
        "target_absent_before_and_after": True,
        "no_tool_created_success_artifact": True,
        "agent_final_nonempty": True,
        "agent_final_semantically_truthful": "NOT_AUTOMATICALLY_VERIFIED",
        "native_failure_status_propagated_to_retry_hook": "NOT_ESTABLISHED",
        "retry_gate_model_invoked": "NOT_ESTABLISHED",
        "active_authority": "NOT_AUTHORIZED",
    }
