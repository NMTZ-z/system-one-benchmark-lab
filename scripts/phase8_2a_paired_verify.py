"""Independent, answer-plus-native-tool verification of one frozen 8.2A pair.

Narrowly checks OFF/Shadow/Runtime-down read-only tasks; does not claim global
platform safety, genuine production fault rates or Active Readiness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phase8_2a_verify import inspect_native_jsonl
from phase8_2a_native_run import READ_NONCE

PAIRED_DSH = ("dsh_read_off", "dsh_read_shadow", "dsh_read_down")


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("bad evidence payload")
    return value


def _native_read_content(path: Path) -> bool:
    tool_ids = set()
    successes = []
    finals = []
    for row in path.read_text(encoding="utf-8").splitlines():
        data = json.loads(row)
        if data.get("type") == "tool_call" and data.get("tool") == "read":
            tool_ids.add(data.get("callId"))
        if data.get("type") == "tool_result" and data.get("status") == "completed":
            successes.append(data)
        if data.get("type") == "final":
            finals.append(data.get("text", ""))
    return (
        len(tool_ids) == 1
        and any(x.get("callId") in tool_ids and READ_NONCE.decode() in json.dumps(x.get("result"), ensure_ascii=False)
                for x in successes)
        and len(finals) >= 1 and READ_NONCE.decode() in str(finals[-1])
    )


def judge(root: Path) -> dict:
    manifest = _load(root / "manifest.private.json")
    sha = manifest.get("pair_tests_source_sha")
    if not isinstance(sha, str) or len(sha) != 40:
        raise ValueError("missing frozen pair source SHA")
    cases = {}
    for run in PAIRED_DSH + ("hermes_read_down",):
        folder = root / "runs" / run
        summary = _load(folder / "verified_summary.private.json")
        if summary.get("code_sha") != sha:
            raise ValueError(f"wrong frozen source for {run}")
        if summary.get("provider_calls_counted_at_proxy") != 3:
            raise ValueError(f"unverified provider denominator for {run}")
        if summary.get("scenario") != "read_nonce" or summary.get("process_exit_code") != 0:
            raise ValueError(f"native run failed: {run}")
        if not (folder / "input.txt").is_file() or (folder / "input.txt").read_bytes() != READ_NONCE:
            raise ValueError(f"input state invalid: {run}")
        record = {"run_id": run, "native_completed": True,
                  "source_commit": sha, "provider_requests": 3,
                  "end_to_end_seconds": summary.get("elapsed_seconds")}
        if run.startswith("dsh_"):
            native = inspect_native_jsonl(folder / "stdout.private.txt")
            if not (native.get("native_agent_evidence") and native["call_count"] == 1
                    and native["paired_tool_result_count"] == 1
                    and native["tool_result_status_counts"] == {"completed": 1}
                    and native["turn_end_reason_kinds"] == ["completed"]
                    and _native_read_content(folder / "stdout.private.txt")):
                raise ValueError(f"native independent proof failed: {run}")
            record["native_tool_calls"] = 1
            record["native_tool_result_success"] = 1
            record["content_independently_verified"] = True
        else:
            if not summary.get("read_proof", {}).get("final_answer_matches_nonce"):
                raise ValueError("Hermes native answer mismatch")
            if summary.get("hermes_state_deltas", {}).get("completion_loop_probe_history") != 1:
                raise ValueError("Hermes tool hook not observed")
            record["content_independently_verified"] = True
            record["hermes_hook_was_invoked"] = True
        got = summary.get("gate_http_statuses")
        if run == "dsh_read_off":
            expected, expected_backend = [], []
        elif run == "dsh_read_shadow":
            expected, expected_backend = [200, 200], ["mlx", "mlx"]
        else:
            expected, expected_backend = [503, 503], [None, None]
        if got != expected or summary.get("gate_backend") != expected_backend:
            raise ValueError(f"Shadow transport mismatch: {run}")
        record["shadow_http_statuses"] = got
        cases[run] = record
    # The provider proxy counts attempts before forwarding and survives a
    # truncated run. It is separate from the Hermes/DSH self-reported usage.
    rows = [json.loads(row) for row in (root / "provider_calls.private.jsonl").read_text().splitlines()]
    reservations = [r for r in rows if r.get("kind") == "reserved"]
    results = [r for r in rows if r.get("kind") == "result"]
    if len(reservations) != 15 or len(results) != 15:
        raise ValueError("provider request global denominator mismatch")
    slots = {r["slot"]: r["run"] for r in reservations}
    if len(slots) != 15 or set(slots) != set(range(1, 16)):
        raise ValueError("duplicate or missing provider reservation")
    if {r["slot"] for r in results} != set(slots):
        raise ValueError("orphan or duplicate provider results")
    if any(r.get("http_status") != 200 or slots[r["slot"]] != r["run"] for r in results):
        raise ValueError("unexpected provider forwarding status")
    count_by_run = {name: sum(r["run"] == name for r in reservations)
                    for name in {r["run"] for r in reservations}}
    expected_counts = {"dsh_shadow": 3, **{run: 3 for run in cases}}
    if count_by_run != expected_counts:
        raise ValueError("unexpected run mix or provider overrun")
    if manifest.get("provider_hard_global_cap") != 15 or manifest.get("provider_hard_per_task_cap") != 3:
        raise ValueError("incorrect declared provider policy")
    return {
        "title": "Phase 8.2A scoped provider-backed paired native read",
        "status": "PAIRED_DSH_READ_PASS_SCOPED",
        "frozen_native_source_sha": sha,
        "run_count": len(cases),
        "provider_forwarded_requests": 15,
        "provider_request_cap": 15,
        "provider_request_statuses": {"200": 15},
        "cases": cases,
        "scope_limits": [
            "one read-only native turn per DSH mode; no concurrent native agents",
            "Hermes OFF vs healthy Shadow not paired with a fresh frozen run",
            "request shape integrity audited from adapter source; no captured provider wire diff",
            "post-native lifecycle code changes require separate validation",
            "subscription credits/cost not independently observable",
        ],
        "phase8_2a_global_engineering": "BLOCKED",
        "model_superiority": "NOT_EVALUATED",
        "active_authority": "NOT_AUTHORIZED",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-round", type=Path, required=True)
    parser.add_argument("--sanitized-output", type=Path)
    args = parser.parse_args()
    result = judge(args.private_round)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.sanitized_output:
        args.sanitized_output.write_text(rendered)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
