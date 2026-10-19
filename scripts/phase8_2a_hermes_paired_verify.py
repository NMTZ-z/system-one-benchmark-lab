"""Independently verify real native Hermes OFF/healthy/down from private evidence.

Read-only: combines the native Hermes isolated SQLite session/tool records,
per-run independent input byte oracles, the separate real StepFun transport
ledger and the privacy-safe real Runtime HTTP collector. Never exports keys,
prompts, tool content, call IDs, or native Session IDs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

FROZEN_SOURCE_SHA = "9120c98a7373d7de6e32f7024eb11b4e4d25cec0"
MODEL = "stepfun/step-5-preview"
PROXY_ORIGIN = "http://127.0.0.1:18794"
CASES = ("hermes_off", "hermes_shadow", "hermes_down")
EXPECTED_HTTP = {"hermes_off": [], "hermes_shadow": [200, 200], "hermes_down": [503, 503]}
EXPECTED_BACKENDS = {"hermes_off": [], "hermes_shadow": ["mlx", "mlx"], "hermes_down": [None, None]}


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return data


def _read_jsonl(path: Path) -> list[dict]:
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("invalid JSONL object")
        values.append(value)
    if not values:
        raise ValueError("missing audit JSONL evidence")
    return values


def _native_sqlite_evidence(db: sqlite3.Connection, run_dir: Path, nonce: str) -> dict:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id,tool_call_count,api_call_count,billing_base_url,end_reason "
        "FROM sessions WHERE cwd=?", (str(run_dir.resolve()),),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("missing or ambiguous native Hermes isolated Session")
    row = rows[0]
    if (row["tool_call_count"] != 1 or row["api_call_count"] != 2
            or row["billing_base_url"] != PROXY_ORIGIN
            or row["end_reason"] != "agent_close"):
        raise ValueError("Hermes native Session tool count / loopback Provider / termination invalid")
    messages = db.execute(
        "SELECT role,content,tool_call_id,tool_calls,tool_name "
        "FROM messages WHERE session_id=? ORDER BY timestamp,id", (row["id"],),
    ).fetchall()
    user = [x for x in messages if x["role"] == "user"]
    calls = [x for x in messages if x["role"] == "assistant" and x["tool_calls"]]
    results = [x for x in messages if x["role"] == "tool"]
    final = [x for x in messages if x["role"] == "assistant" and not x["tool_calls"]]
    if not (len(user) == len(calls) == len(results) == len(final) == 1):
        raise ValueError("native Hermes message lifecycle incomplete or ambiguous")
    if nonce in str(user[0]["content"]):
        raise ValueError("expected hidden file content was present in task prompt")
    try:
        raw_calls = json.loads(calls[0]["tool_calls"])
    except (ValueError, TypeError):
        raise ValueError("native Hermes tool-call metadata malformed") from None
    if not isinstance(raw_calls, list) or len(raw_calls) != 1:
        raise ValueError("native Hermes call count invalid")
    call = raw_calls[0]
    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
        raise ValueError("native Hermes tool call is not a structured function")
    if (call["function"].get("name") != "read_file"
            or results[0]["tool_name"] != "read_file"
            or not isinstance(call.get("id"), str) or not call["id"]
            or results[0]["tool_call_id"] != call["id"]):
        raise ValueError("Hermes native read_file call/result identity mismatch")
    if nonce not in str(results[0]["content"]):
        raise ValueError("independent native read_file tool result did not return expected file bytes")
    if nonce not in str(final[0]["content"]):
        raise ValueError("native Hermes final answer did not match independent input")
    return {
        "native_tool_name": "read_file",
        "native_tool_call_result_id_paired": True,
        "native_tool_result_matches_original_file": True,
        "agent_final_matches_original_file": True,
        "hidden_oracle_absent_from_task_prompt": True,
        "original_provider_route_verified": True,
        "native_session_normal_close": True,
    }


def verify(round_dir: Path, *, hermes_home: Path) -> dict:
    manifest = _read_json(round_dir / "manifest.private.json")
    if (manifest.get("code_sha") != FROZEN_SOURCE_SHA
            or manifest.get("provider_hard_cap_total") != 9
            or manifest.get("provider_hard_cap_per_case") != 3
            or manifest.get("cases") != list(CASES)):
        raise ValueError("wrong frozen source or undeclared Provider budget")
    if not manifest.get("no_new_paid_service") or not manifest.get("source_equals_prior_real_hermes_adapter"):
        raise ValueError("missing independent provider/source safety declarations")
    db_path = hermes_home / "state.db"
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    evidence = {}
    with sqlite3.connect(uri, uri=True) as db:
        for index, case in enumerate(CASES):
            folder = round_dir / "runs" / case
            metadata = _read_json(folder / "verified_summary.private.json")
            nonce_bytes = (folder / "input.txt").read_bytes()
            nonce = nonce_bytes.decode("utf-8")
            if not nonce.startswith("P82A_NATIVE_READ_NONCE_"):
                raise ValueError("input is not an audited hidden fixture")
            if (metadata.get("code_sha") != FROZEN_SOURCE_SHA
                    or metadata.get("run_id") != case
                    or metadata.get("platform") != "hermes"
                    or metadata.get("main_model") != MODEL
                    or metadata.get("scenario") != "read_nonce"):
                raise ValueError("Hermes run identity/source/model mismatch")
            if metadata.get("mode") != ("off" if index == 0 else "shadow"):
                raise ValueError("native gate mode mismatch")
            if (metadata.get("process_exit_code") != 0 or metadata.get("timed_out") is not False
                    or not metadata.get("input_unchanged")
                    or not metadata.get("read_proof", {}).get("final_answer_matches_nonce")):
                raise ValueError("native Hermes run or independent file check failed")
            if (metadata.get("provider_calls_counted_at_proxy") != 3
                    or metadata.get("provider_global_used") != 3 * (index + 1)):
                raise ValueError("Provider network request count / run ordering invalid")
            if (metadata.get("gate_http_statuses") != EXPECTED_HTTP[case]
                    or metadata.get("gate_backend") != EXPECTED_BACKENDS[case]):
                raise ValueError("System One Runtime gate statuses invalid")
            changes = metadata.get("hermes_state_deltas", {})
            wanted = 0 if index == 0 else 1
            if (changes.get("completion_shadow_history") != wanted
                    or changes.get("completion_loop_probe_history") != wanted
                    or changes.get("retry_escalation_shadow_history") != 0):
                raise ValueError("Completion/Retry Shadow hook accounting mismatch")
            usage = metadata.get("usage", {})
            if usage.get("api_calls") != 2 or usage.get("completed") is not True:
                raise ValueError("Hermes self-reported main-model count/status unexpected")
            proof = _native_sqlite_evidence(db, folder, nonce)
            evidence[case] = {
                "mode": metadata["mode"],
                "native_agent_completed": True,
                **proof,
                "runtime_http_statuses": EXPECTED_HTTP[case],
                "runtime_mlx_decisions": 2 if index == 1 else 0,
                "runtime_degraded_503": 2 if index == 2 else 0,
                "runtime_observer_loop_probe_delta": wanted,
                "runtime_observer_turn_end_delta": wanted,
                "provider_real_forwarded_request_count": 3,
                "native_main_model_api_calls_reported": 2,
                "elapsed_seconds": metadata.get("elapsed_seconds"),
            }
    # Separate network ledger; raw Agent and raw Provider bodies not involved.
    rows = _read_jsonl(round_dir / "provider_calls.private.jsonl")
    reservations = [v for v in rows if v.get("kind") == "reserved"]
    finalized = [v for v in rows if v.get("kind") == "result"]
    if len(reservations) != 9 or len(finalized) != 9:
        raise ValueError("real Provider network denominator invalid")
    def slots(items: list[dict]) -> list[int]:
        return sorted(int(v["slot"]) for v in items)
    if slots(reservations) != list(range(1, 10)) or slots(finalized) != list(range(1, 10)):
        raise ValueError("duplicate/orphan/missing Provider reservations or responses")
    owners = {v["slot"]: v["run"] for v in reservations}
    if any(v.get("http_status") != 200 or owners[v["slot"]] != v.get("run") for v in finalized):
        raise ValueError("Provider HTTPS status or per-run owner mismatch")
    counted = dict(Counter(v.get("run") for v in reservations))
    if counted != {case: 3 for case in CASES}:
        raise ValueError("provider ledger run allocation differs from frozen 3+3+3")
    # Independent Runtime transport recorder: no Session IDs are retained,
    # so event-window/sequence only, not a claim of exact turn-ID join.
    http_events = _read_jsonl(round_dir / "collector_events.private.jsonl")
    if len(http_events) != 4:
        raise ValueError("unexpected number of Shadow HTTP requests")
    if not all(v.get("path") == "/v1/workflows/completion-gate" for v in http_events):
        raise ValueError("unrequested Runtime workflow was invoked")
    if not all(v.get("http_status") == 200 and v.get("backend") == "mlx"
               and v.get("decision_source") == "model" for v in http_events[:2]):
        raise ValueError("healthy Shadow did not use genuine Laya MLX")
    if not all(v.get("http_status") == 503 and v.get("backend") is None
               for v in http_events[2:]):
        raise ValueError("Runtime-down Shadow did not fail-open via 503")
    return {
        "schema": "phase8.2a-hermes-native-paired-read-v1",
        "status": "SCOPED_HERMES_OFF_SHADOW_DOWN_NATIVE_PASS",
        "frozen_executable_source_sha": FROZEN_SOURCE_SHA,
        "main_model": MODEL,
        "model_route": "existing StepFun Plan Step 5 Preview",
        "decision_runtime": "real Laya/MLX for healthy Shadow",
        "native_Hermes_version": manifest.get("canonical_hermes_client"),
        "cases": evidence,
        "provider_hard_cap": {"requested_max": 9, "actually_reserved": 9,
                              "finalized_upstream_http200": 9, "per_run": counted,
                              "all_incoming_requests_accounted_for_at_budget_proxy": True,
                              "actual_subscription_credit_spend": "unknown"},
        "shadow_runtime_HTTP": {"healthy_completion_mlx_200": 2,
                                "degraded_completion_503": 2,
                                "off_runtime_requests": 0,
                                "retry_requests_in_read_success_trio": 0},
        "independent_provenance": {
            "Hermes_native_Session_SQLite_inspected": True,
            "read_file_call_and_tool_result_ID_matched": True,
            "hidden_input_file_and_tool_result_match": True,
            "user_task_prompt_did_not_include_expected_file_bytes": True,
            "native_final_message_checked": True,
            "Provider_proxy_durable_ledger_checked": True,
            "Runtime_metadata_only_HTTP_collector_checked": True,
            "no_raw_secret_or_Session_ID_published": True,
        },
        "limitations": [
            "One isolated native read-only task per mode; not every Hermes tool class tested",
            "Sequential mode conditions with separate native Hermes Agent invocations; no randomized performance claims",
            "Hermes per-session usage counters differ from authoritative proxy count, so no inferred breakdown of unmatched auxiliary/retry requests",
            "Privacy-safe HTTP collector cannot independently join exact individual Runtime call to native Session ID",
            "Does not establish Active/Canary safety, model superiority or subscription monetary cost",
        ],
        "model_superiority": "NOT_EVALUATED",
        "active_authority": "NOT_AUTHORIZED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-round", required=True, type=Path)
    parser.add_argument("--private-hermes-home", required=True, type=Path)
    parser.add_argument("--sanitized-output", type=Path)
    args = parser.parse_args()
    summary = verify(args.private_round, hermes_home=args.private_hermes_home)
    value = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    if args.sanitized_output:
        args.sanitized_output.write_text(value, encoding="utf-8")
    else:
        print(value)


if __name__ == "__main__":
    main()
