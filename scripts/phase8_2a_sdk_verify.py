"""Fail-closed native SDK/real-Provider evidence verifier, NO model calls.

The only public output is a fixed-metadata, privacy-safe summary. Native JSON-RPC
frames, user messages, session IDs, tool text and original files stay private.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

FROZEN_NATIVE_SHA = "3d5b02fdb7d489c80de4ab958fd33a559b33e08c"
REAL_MAIN_MODEL = "stepfun/step-5-preview"
PRIMARY_SESSION = "p82sdk-main"
PARALLEL_SESSION = "p82sdk-side"


def _json(path: Path) -> dict:
    v = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(v, dict):
        raise ValueError(f"not a JSON object: {path.name}")
    return v


def _jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError("JSONL includes a non-object event")
        out.append(obj)
    if not out:
        raise ValueError("missing native or network event evidence")
    return out


def _rpc_response(frames: list[dict], idx: int) -> None:
    match = [v for v in frames if v.get("id") == idx]
    if len(match) != 1 or not isinstance(match[0].get("result"), dict) or match[0].get("error"):
        raise ValueError("native SDK RPC response missing, duplicated or failed")


def _event(frames: list[dict], sid: str, turn: int, name: str) -> list[tuple[int, dict]]:
    result = []
    for idx, frame in enumerate(frames):
        if frame.get("method") != "session.event":
            continue
        params = frame.get("params", {})
        if not isinstance(params, dict) or params.get("sessionId") != sid:
            continue
        entry = params.get("event", {})
        if not isinstance(entry, dict) or entry.get("type") != name:
            continue
        data = entry.get("data", {})
        if isinstance(data, dict) and data.get("turn") == turn:
            result.append((idx, entry))
    return result


def _turn(frames: list[dict], sid: str, turn: int, *, success: bool,
          expected_content: str | None = None) -> dict:
    starts, ends = _event(frames, sid, turn, "turn/start"), _event(frames, sid, turn, "turn/end")
    calls, results = _event(frames, sid, turn, "tool/call"), _event(frames, sid, turn, "tool/result")
    if not (len(starts) == len(ends) == len(calls) == len(results) == 1):
        raise ValueError("native SDK events must have exactly one start/end and paired read")
    call, result = calls[0][1], results[0][1]
    cdata, rdata = call.get("data", {}), result.get("data", {})
    message = rdata.get("message", {})
    if not isinstance(cdata, dict) or not isinstance(message, dict):
        raise ValueError("native SDK tool payload missing")
    source = message.get("source", {})
    if (cdata.get("name") != "read" or not isinstance(source, dict)
            or not isinstance(cdata.get("callId"), str)
            or not cdata.get("callId") or cdata["callId"] != source.get("callId")):
        raise ValueError("native tool name, exact call ID or result ID invalid")
    if message.get("isError") is not (not success):
        raise ValueError("native tool result error status inconsistent with scenario")
    reason = ends[0][1].get("data", {}).get("reason", {}).get("kind")
    if reason != "completed":
        raise ValueError("native Agent turn did not complete")
    if not starts[0][0] < calls[0][0] < results[0][0] < ends[0][0]:
        raise ValueError("native lifecycle event order invalid")
    if success:
        if not expected_content or expected_content not in json.dumps(message.get("content", []), ensure_ascii=False):
            raise ValueError("native tool result did not independently contain file content")
        answer = _event(frames, sid, turn, "assistant/message")
        if not any(expected_content in json.dumps(e.get("data", {}).get("message", {}).get("content", []), ensure_ascii=False)
                   for _, e in answer):
            raise ValueError("native final assistant content did not match file content")
    return {
        "native_turn": turn,
        "native_tool": "read",
        "tool_result": "completed" if success else "error",
        "native_call_result_id_paired": True,
        "native_turn_completed": True,
        "independent_read_content_verified": success,
        "start_frame_index": starts[0][0],
        "end_frame_index": ends[0][0],
    }


def _sanitize(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in {"start_frame_index", "end_frame_index"}}


def verify(root: Path) -> dict:
    manifest = _json(root / "manifest.private.json")
    if manifest.get("frozen_executable_source") != FROZEN_NATIVE_SHA:
        raise ValueError("wrong frozen runtime/adapter source")
    if manifest.get("main_model") != REAL_MAIN_MODEL:
        raise ValueError("unexpected provider or model in manifest")
    if manifest.get("provider_budget_total") != 12:
        raise ValueError("provider budget not predeclared")
    rdir = root / "runs"
    resident = rdir / "sdk_resident"
    frames = _jsonl(resident / "sdk_events.private.jsonl")
    for number in (1, 2, 3, 4, 5):
        _rpc_response(frames, number)
    for file in ("input_primary.txt", "input_parallel.txt"):
        if not (resident / file).is_file():
            raise ValueError("private read input file missing")
    nonce_a = (resident / "input_primary.txt").read_text(encoding="utf-8")
    nonce_b = (resident / "input_parallel.txt").read_text(encoding="utf-8")
    if nonce_a == nonce_b or not nonce_a.startswith("P82A_NATIVE_SDK_") or not nonce_b.startswith("P82A_NATIVE_SDK_"):
        raise ValueError("hidden task content did not match frozen fixture family")
    if (resident / "nonexistent_first_turn.txt").exists():
        raise ValueError("native failure task unexpectedly created the target")
    first = _turn(frames, PRIMARY_SESSION, 1, success=False)
    second = _turn(frames, PRIMARY_SESSION, 2, success=True, expected_content=nonce_a)
    side = _turn(frames, PARALLEL_SESSION, 1, success=True, expected_content=nonce_b)
    if not (second["start_frame_index"] < side["start_frame_index"] < second["end_frame_index"]):
        raise ValueError("separate native Session was not active during primary Turn 2")
    if not (first["end_frame_index"] < second["start_frame_index"]):
        raise ValueError("primary Session's two Turns overlapped unexpectedly")
    first_record = _json(resident / "result.private.json")
    if first_record.get("test_status") != "SCOPED_NATIVE_RESIDENT_PROCESS_PASS":
        raise ValueError("resident SDK driver did not report successful completion")
    if first_record.get("provider_calls") != 6 or not first_record.get("same_os_pid_process"):
        raise ValueError("SDK runner process or provider counts mismatch")

    outcomes = {
        "resident_primary_failed_read": _sanitize(first),
        "resident_primary_successful_read": _sanitize(second),
        "resident_overlapping_other_session": _sanitize(side),
    }
    for mode in ("off", "down"):
        folder = rdir / ("dsh_sdk_" + mode)
        entries = _jsonl(folder / "sdk_events.private.jsonl")
        for n in (1, 2, 3):
            _rpc_response(entries, n)
        raw_file = folder / "input.txt"
        if not raw_file.is_file():
            raise ValueError("SDK mode read file absent")
        expected = raw_file.read_text(encoding="utf-8")
        if not expected.startswith("P82A_SDK_COMPARE_READ_"):
            raise ValueError("mode comparison file content unrecognized")
        proof = _turn(entries, "p82sdk_" + mode, 1, success=True, expected_content=expected)
        saved = _json(folder / "independent_summary.private.json")
        if (not saved.get("tool_ids_paired") or not saved.get("native_tool_result_success")
                or not saved.get("final_message_matches_content")
                or saved.get("sdk_process_exit_code") != 0 or saved.get("provider_requests") != 2):
            raise ValueError("actual OFF/degraded runner did not verify native completion")
        if saved.get("gate_events_during_run") != (0 if mode == "off" else 2):
            raise ValueError("OFF/degraded no-change evidence inconsistent")
        outcomes["sdk_" + mode + "_read"] = _sanitize(proof)

    provider_rows = _jsonl(root / "provider_calls.private.jsonl")
    reservations = [r for r in provider_rows if r.get("kind") == "reserved"]
    finalized = [r for r in provider_rows if r.get("kind") == "result"]
    if len(reservations) != 10 or len(finalized) != 10:
        raise ValueError("provider request denominator mismatch")
    reserved_ids = [r.get("slot") for r in reservations]
    finished_ids = [r.get("slot") for r in finalized]
    if sorted(reserved_ids) != list(range(1, 11)) or sorted(finished_ids) != list(range(1, 11)):
        raise ValueError("orphan/duplicate/missing provider forwarding slots")
    by_slot = {r["slot"]: r.get("run") for r in reservations}
    if any(r.get("http_status") != 200 or by_slot[r["slot"]] != r.get("run") for r in finalized):
        raise ValueError("provider forwarding failed or slot owner mismatch")
    provider_counts = dict(Counter(r.get("run") for r in reservations))
    if provider_counts != {"dsh_sdk_resident": 6, "dsh_sdk_off": 2, "dsh_sdk_down": 2}:
        raise ValueError("provider budget allocation mismatched frozen scenarios")
    log = _jsonl(root / "collector_events.private.jsonl")
    if len(log) != 9:
        raise ValueError("Shadow Runtime HTTP denominator mismatch")
    success_gate = log[:7]
    degraded_gate = log[7:]
    if sum(r.get("workflow") == "completion_gate" and r.get("http_status") == 200 and r.get("backend") == "mlx" and r.get("decision_source") == "model" for r in success_gate) != 6:
        raise ValueError("real Laya Completion inference count invalid")
    if sum(r.get("workflow") == "retry_escalation_gate" and r.get("http_status") == 200 and r.get("backend") == "rule" for r in success_gate) != 1:
        raise ValueError("real Retry Shadow rule count invalid")
    if any(r.get("http_status") != 503 for r in degraded_gate):
        raise ValueError("expected two intentionally degraded Shadow attempts")
    return {
        "schema": "local-system-one-phase8.2a-native-sdk-live-v1",
        "phase": "8.2A", "status": "SCOPED_DSH_NATIVE_SDK_RESIDENT_AND_OFF_DOWN_PASS",
        "frozen_runtime_adapter_sha": FROZEN_NATIVE_SHA,
        "main_model": REAL_MAIN_MODEL,
        "main_provider_route": "already-authorized StepFun Plan /step_plan/v1",
        "decision_model_runtime": "real Laya/MLX",
        "native_dsh_platform_sha": manifest.get("pinned_dsh"),
        "sdk_single_live_process": True,
        "sdk_same_session_sequential_turns": [1, 2],
        "sdk_two_distinct_sessions_start_overlapped": True,
        "native_scenarios": outcomes,
        "off_shadow_gate_requests": 0,
        "healthy_runtime": {"completion_real_mlx_http_200": 6, "retry_conservative_rule_http_200": 1},
        "runtime_down": {"completion_http_503": 2, "native_read_completed": True},
        "provider_network_budget": {
            "declared_global_cap": 12, "actual_reserved_and_completed": 10,
            "actual_upstream_http_200": 10,
            "by_run": provider_counts,
            "hard_cap_not_exceeded": True,
            "unused_limit_slots_not_subscription_credits": 2,
            "monetary_plan_credit_usage": "unknown",
        },
        "independent_checks": {
            "raw_native_event_frames_read": True, "all_native_tool_ids_matched": True,
            "input_file_contents_independently_verified": True,
            "native_task_results_and_final_assistant_messages_verified": True,
            "provider_slot_cardinality_confirmed": True,
            "runtime_telemetry_counts_confirmed": True,
            "no_public_secrets_or_session_identifiers": True,
        },
        "limitations": [
            "Latest Hermes OFF/Shadow/Runtime-down native suite not authorized/finished after access block",
            "Two SDK Session turns overlapped; true simultaneously executing tool calls not independently proven",
            "Healthy SDK run used multiple sessions in one SDK process; OFF and down use separately isolated SDK processes",
            "No high-volume long-duration concurrent Agent stress test or statistical noninterference guarantee",
            "No direct turn-to-Runtime HTTP correlation ID in privacy-safe collector",
            "No Active authority, Laya model superiority claim or provider-credit accounting",
        ],
        "phase8_2a_engineering": "BLOCKED",
        "model_superiority": "NOT_EVALUATED",
        "active_authority": "NOT_AUTHORIZED",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-round", type=Path, required=True)
    p.add_argument("--sanitized-output", type=Path)
    opts = p.parse_args()
    result = verify(opts.private_round)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if opts.sanitized_output:
        opts.sanitized_output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
