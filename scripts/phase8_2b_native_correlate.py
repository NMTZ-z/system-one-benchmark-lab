"""Phase 8.2B *private* native-to-HTTP correlation validator, no Agent/LLM calls.

Inputs MUST stay in isolated private storage; output contains only bounded,
allowlisted counts/opaque refs. It does not prove task success or Provider cost.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

SCOPES = frozenset({"session", "turn", "native_event", "tool_call", "decision_request"})
HEX_REF = re.compile(r"^[a-f0-9]{32}$")
MAX_ROWS = 2000


class CorrelationError(ValueError):
    """Invalid input, identity conflict or unsupported evidence."""


def ref(key: bytes, scope: str, raw: str) -> str:
    if not isinstance(key, bytes) or len(key) != 32 or scope not in SCOPES:
        raise CorrelationError("invalid private reference config")
    if not isinstance(raw, str) or not 0 < len(raw) <= 1024:
        raise CorrelationError("invalid private identity")
    return hmac.new(key, (scope + "\x00" + raw).encode(), hashlib.sha256).hexdigest()[:32]


def _dsh_native(frames: list[dict], key: bytes) -> tuple[dict[str, dict], list[str]]:
    """Validate native SDK lifecycle and exact tool-call/result identities.

    There is no join by timestamps. Out-of-order input lines are acceptable,
    but a tool/result without a native tool/call is not a verified tool.
    """
    found: dict[str, dict] = {}
    issues: list[str] = []
    native_calls: set[tuple[str, int, str]] = set()
    native_results: set[tuple[str, int, str]] = set()
    started: set[tuple[str, int]] = set()
    ended: set[tuple[str, int]] = set()
    normalized: list[tuple[str, int, str, dict]] = []
    for frame in frames:
        if not isinstance(frame, dict) or frame.get("method") != "session.event":
            continue
        params = frame.get("params")
        if not isinstance(params, dict):
            continue
        sid, event = params.get("sessionId"), params.get("event")
        if not isinstance(event, dict) or not isinstance(sid, str) or not sid:
            issues.append("invalid_native_event_identity")
            continue
        name = event.get("type")
        if name not in {"turn/start", "turn/end", "tool/call", "tool/result"}:
            continue
        data = event.get("data")
        if not isinstance(data, dict) or type(data.get("turn")) is not int or data["turn"] < 1:
            issues.append("native_turn_identity_missing")
            continue
        turn = data["turn"]
        normalized.append((sid, turn, name, data))
        identity = (sid, turn)
        if name == "turn/start":
            if identity in started:
                issues.append("duplicate_native_turn_start")
            started.add(identity)
        elif name == "turn/end":
            if identity in ended:
                issues.append("duplicate_native_turn_end")
            ended.add(identity)
        elif name == "tool/call":
            call = data.get("callId")
            if not isinstance(call, str) or not 0 < len(call) <= 256:
                issues.append("native_tool_call_id_missing")
            elif (sid, turn, call) in native_calls:
                issues.append("duplicate_native_tool_call")
            else:
                native_calls.add((sid, turn, call))
        else:
            message = data.get("message")
            source = message.get("source") if isinstance(message, dict) else None
            call = source.get("callId") if isinstance(source, dict) else None
            if not isinstance(call, str) or not 0 < len(call) <= 256:
                issues.append("native_tool_result_call_id_missing")
            elif (sid, turn, call) in native_results:
                issues.append("duplicate_native_tool_result")
            else:
                native_results.add((sid, turn, call))
    if native_results - native_calls:
        issues.append("unpaired_native_tool_result")
    if native_calls - native_results:
        issues.append("native_tool_result_missing")
    if ended - started:
        issues.append("native_turn_start_missing")
    if started - ended:
        issues.append("native_turn_end_missing")

    for sid, turn, name, data in normalized:
        if name not in {"tool/result", "turn/end"}:
            continue
        stage = "tool_result" if name == "tool/result" else "turn_end"
        raw = sid + "\x00" + str(turn) + "\x00" + stage
        if stage == "tool_result":
            message = data.get("message")
            source = message.get("source") if isinstance(message, dict) else None
            call = source.get("callId") if isinstance(source, dict) else None
            if not isinstance(call, str) or not call or (sid, turn, call) not in native_calls:
                continue
            raw += "\x00" + call
        try:
            identity = ref(key, "native_event", raw)
            entry = {
                "native_event_ref": identity,
                "session_ref": ref(key, "session", sid),
                "turn_ref": ref(key, "turn", sid + "\x00" + str(turn)),
                "native_stage": stage,
            }
        except CorrelationError:
            issues.append("native_identity_invalid")
            continue
        if identity in found:
            issues.append("duplicate_native_identity")
        else:
            found[identity] = entry
    return found, issues


def _hermes_native(db_path: Path, key: bytes) -> tuple[dict[str, dict], list[str]]:
    found: dict[str, dict] = {}
    issues: list[str] = []
    # URI read-only and immutable; no creating/repairing production SQLite.
    uri = "file:" + db_path.resolve().as_posix() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as db:
        rows = db.execute("SELECT id,end_reason FROM sessions").fetchall()
        for sid, end_reason in rows:
            if not isinstance(sid, str) or not sid:
                issues.append("native_session_identity_missing")
                continue
            try:
                sidref = ref(key, "session", sid)
            except CorrelationError:
                issues.append("native_session_identity_invalid")
                continue
            calls = db.execute(
                "SELECT tool_call_id FROM messages WHERE session_id=? AND role='tool'",
                (sid,),
            ).fetchall()
            for (cid,) in calls:
                if not isinstance(cid, str) or not cid:
                    issues.append("native_tool_result_call_id_missing")
                    continue
                toolref = ref(key, "tool_call", sid + "\x00" + cid)
                if toolref in found:
                    issues.append("duplicate_native_identity")
                found[toolref] = {
                    "session_ref": sidref, "tool_call_ref": toolref,
                    "native_stage": "tool_result",
                }
            # A single-read isolated session may have one final boundary. A
            # multi-turn session needs explicit platform Turn identity, which
            # legacy Hermes SQLite alone cannot establish.
            native_turns = db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id=? AND role='user'",
                (sid,),
            ).fetchone()[0]
            if native_turns != 1:
                issues.append("hermes_session_turn_identity_ambiguous")
            if end_reason == "agent_close" and native_turns == 1:
                found["end:" + sidref] = {
                    "session_ref": sidref, "native_stage": "turn_end",
                    "native_end_reason": "agent_close",
                }
    return found, issues


def correlate(platform: str, native: list[dict] | Path, adapter: list[dict],
              http: list[dict], key: bytes) -> dict[str, Any]:
    if platform not in {"deepseek_harness", "hermes"}:
        raise CorrelationError("unsupported native platform")
    if not isinstance(adapter, list) or not isinstance(http, list) or (
        len(adapter) > MAX_ROWS or len(http) > MAX_ROWS
    ):
        raise CorrelationError("input collection exceeds safe limit")
    if platform == "deepseek_harness":
        if not isinstance(native, list) or len(native) > MAX_ROWS:
            raise CorrelationError("expected bounded native SDK frames")
        events, problems = _dsh_native(native, key)
    else:
        if not isinstance(native, Path) or not native.is_file():
            raise CorrelationError("private isolated SQLite not found")
        events, problems = _hermes_native(native, key)
    proxy_refs: dict[str, list[dict]] = {}
    for row in http:
        if not isinstance(row, dict):
            raise CorrelationError("malformed HTTP observation")
        request_ref = row.get("decision_request_ref")
        if request_ref is not None and not (isinstance(request_ref, str) and HEX_REF.fullmatch(request_ref)):
            raise CorrelationError("unsafe HTTP request reference")
        if request_ref:
            proxy_refs.setdefault(request_ref, []).append(row)
    seen_requests: set[str] = set()
    claimed_requests = {
        r.get("decision_request_ref") for r in adapter
        if isinstance(r, dict) and r.get("gate") == "completion"
        and isinstance(r.get("decision_request_ref"), str)
    }
    observed = 0
    verified = 0
    partial = 0
    rows_out: list[dict] = []
    for row in adapter:
        if not isinstance(row, dict):
            raise CorrelationError("malformed Adapter evidence")
        if row.get("gate") != "completion":
            continue
        observed += 1
        stage = row.get("native_stage")
        sidref = row.get("session_ref")
        dr = row.get("decision_request_ref")
        if (not isinstance(sidref, str) or not HEX_REF.fullmatch(sidref)
                or not isinstance(dr, str) or not HEX_REF.fullmatch(dr)):
            partial += 1
            problems.append("adapter_correlation_identity_missing")
            continue
        matched_native = False
        if platform == "deepseek_harness":
            nref = row.get("native_event_ref")
            n = events.get(nref) if isinstance(nref, str) else None
            if n and n["turn_ref"] != row.get("turn_ref"):
                problems.append("cross_turn_identity_conflict")
            matched_native = bool(n and n["session_ref"] == sidref
                                  and n["turn_ref"] == row.get("turn_ref")
                                  and n["native_stage"] == stage)
        elif stage == "tool_result":
            callref = row.get("tool_call_ref")
            n = events.get(callref) if isinstance(callref, str) else None
            matched_native = bool(n and n["session_ref"] == sidref and n["native_stage"] == stage)
        elif stage == "turn_end":
            n = events.get("end:" + sidref)
            matched_native = bool(n and n["native_stage"] == "turn_end")
        network = proxy_refs.get(dr, [])
        if len(network) > 1:
            problems.append("duplicate_http_request_ref")
        if not matched_native or len(network) != 1:
            partial += 1
            problems.append("native_or_http_link_missing_or_ambiguous")
            continue
        response_matches = network[0].get("response_matches_request_id")
        status = network[0].get("http_status")
        # Actual HTTP 200/other successful response requires an echoed ID to
        # certify full request/response correlation, unlike a 503 transport fail.
        if (response_matches is False or row.get("response_request_id_matches") is False
                or (isinstance(status, int) and 200 <= status < 300 and response_matches is not True)
                or row.get("evidence_status") == "ambiguous"):
            partial += 1
            problems.append("response_request_id_mismatch_or_unproven")
            continue
        if dr in seen_requests:
            partial += 1
            problems.append("duplicate_adapter_request_correlation")
            continue
        seen_requests.add(dr)
        verified += 1
        rows_out.append({
            "session_ref": sidref,
            "decision_request_ref": dr,
            "native_stage": stage,
            "http_status": status if isinstance(status, int) and 100 <= status <= 599 else None,
            "correlation_status": "verified_native_request_link",
        })
    if observed == 0:
        problems.append("no_adapter_completion_observation")
    # Don't silently let an unexpected extra Provider observation into PASS.
    if set(proxy_refs) - claimed_requests:
        problems.append("unmatched_http_observations")
    status = "PASS" if verified > 0 and partial == 0 and not problems else (
        "BLOCKED" if any(x in problems for x in (
            "duplicate_native_identity", "duplicate_adapter_request_correlation",
            "response_request_id_mismatch_or_unproven", "unmatched_http_observations",
            "cross_turn_identity_conflict", "duplicate_http_request_ref",
            "duplicate_native_tool_call", "duplicate_native_tool_result",
            "duplicate_native_turn_start", "duplicate_native_turn_end",
        )) else "PARTIAL"
    )
    return {
        "schema": "local-system-one/native-correlation-v1",
        "platform": platform, "status": status,
        "native_event_refs_observed": len(events),
        "adapter_completion_observations": observed,
        "native_http_pairs_verified": verified,
        "unpaired_adapter_observations": partial,
        "issues": sorted(set(problems)),
        "pairs": rows_out,
        "task_outcome": "UNKNOWN", "agent_execution_outcome": "UNKNOWN",
        "active_readiness": "NOT_AUTHORIZED",
    }


def _jsonl(path: Path) -> list[dict]:
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if not isinstance(record, dict):
                raise CorrelationError("private JSONL contains non-object")
            result.append(record)
        if len(result) > MAX_ROWS:
            raise CorrelationError("private JSONL capacity exceeded")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=["hermes", "deepseek_harness"], required=True)
    parser.add_argument("--private-key-file", required=True, type=Path)
    parser.add_argument("--native", required=True, type=Path,
                        help="isolated SQLite file (Hermes) or native JSONL frames (DSH)")
    parser.add_argument("--adapter", required=True, type=Path,
                        help="private JSONL of isolated plugin observation records")
    parser.add_argument("--http", required=True, type=Path,
                        help="private JSONL from isolated 8.2A Shadow proxy")
    parser.add_argument("--output", required=True, type=Path)
    opts = parser.parse_args()
    try:
        private_root = (Path(__file__).resolve().parents[1] / "private").resolve()
        for target in (
            opts.private_key_file, opts.native, opts.adapter, opts.http, opts.output
        ):
            if not target.resolve().is_relative_to(private_root):
                raise CorrelationError("all input/output paths must be isolated under ignored private/")
        keypath = opts.private_key_file.resolve()
        if keypath.stat().st_mode & 0o077:
            raise CorrelationError("insecure private key file permissions")
        key = keypath.read_bytes()
        if len(key) != 32:
            raise CorrelationError("invalid correlation key size")
        if opts.output.exists():
            raise CorrelationError("refusing to overwrite existing report")
        native = opts.native if opts.platform == "hermes" else _jsonl(opts.native)
        result = correlate(opts.platform, native, _jsonl(opts.adapter), _jsonl(opts.http), key)
        opts.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if result["status"] != "PASS":
            raise SystemExit(2)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        # Never echo paths, IDs or private data to stdout.
        if isinstance(exc, SystemExit):
            raise
        raise SystemExit("native correlation BLOCKED: invalid or incomplete private input") from None


if __name__ == "__main__":
    main()
