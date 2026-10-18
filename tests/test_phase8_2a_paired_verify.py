"""Synthetic *verifier unit* fixtures; NEVER provider-backed Agent evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_paired_verify import judge
from phase8_2a_native_run import READ_NONCE

SHA = "a" * 40


def _fixture(root: Path):
    (root / "manifest.private.json").write_text(json.dumps({
        "pair_tests_source_sha": SHA,
        "provider_hard_global_cap": 15,
        "provider_hard_per_task_cap": 3,
    }))
    for name, mode, expected in (
        ("dsh_read_off", "off", []),
        ("dsh_read_shadow", "shadow", [200, 200]),
        ("dsh_read_down", "shadow", [503, 503]),
        ("hermes_read_down", "shadow", [503, 503]),
    ):
        run = root / "runs" / name
        run.mkdir(parents=True)
        (run / "input.txt").write_bytes(READ_NONCE)
        summary = {
            "code_sha": SHA, "provider_calls_counted_at_proxy": 3,
            "scenario": "read_nonce", "process_exit_code": 0,
            "elapsed_seconds": 10.0, "gate_http_statuses": expected,
            "gate_backend": ["mlx"] * 2 if name == "dsh_read_shadow" else [None] * len(expected),
            "read_proof": {"final_answer_matches_nonce": True},
            "hermes_state_deltas": {"completion_loop_probe_history": 1},
        }
        (run / "verified_summary.private.json").write_text(json.dumps(summary))
        if name.startswith("dsh_"):
            event = [
                {"type": "status", "phase": "turn_start"},
                {"type": "status", "phase": "step_start"},
                {"type": "tool_call", "tool": "read", "callId": "single"},
                {"type": "tool_result", "callId": "single", "status": "completed", "result": {"text": READ_NONCE.decode()}},
                {"type": "status", "phase": "step_end"},
                {"type": "status", "phase": "turn_end", "reason": {"kind": "completed"}},
                {"type": "final", "text": READ_NONCE.decode()},
            ]
            (run / "stdout.private.txt").write_text("\n".join(json.dumps(r) for r in event) + "\n")
    ledger = []
    run_names = ("dsh_shadow", "dsh_read_off", "dsh_read_shadow", "dsh_read_down", "hermes_read_down")
    for slot in range(1, 16):
        name = run_names[(slot - 1) // 3]
        ledger.extend(({"kind": "reserved", "run": name, "slot": slot},
                       {"kind": "result", "run": name, "slot": slot, "http_status": 200}))
    (root / "provider_calls.private.jsonl").write_text("\n".join(json.dumps(row) for row in ledger) + "\n")


def test_paired_verifier_preserves_separate_dsh_and_hermes_claims(tmp_path):
    _fixture(tmp_path)
    report = judge(tmp_path)
    assert report["run_count"] == 4
    assert report["status"] == "PAIRED_DSH_READ_PASS_SCOPED"
    assert report["phase8_2a_global_engineering"] == "BLOCKED"
    assert report["cases"]["dsh_read_off"]["shadow_http_statuses"] == []
    assert report["cases"]["dsh_read_shadow"]["shadow_http_statuses"] == [200, 200]


def test_paired_verifier_rejects_false_native_or_wrong_source(tmp_path):
    _fixture(tmp_path)
    path = tmp_path / "runs/dsh_read_shadow/stdout.private.txt"
    data = path.read_text().splitlines()
    path.write_text("\n".join(l for l in data if json.loads(l).get("type") != "tool_result"))
    with pytest.raises(ValueError, match="native independent proof"):
        judge(tmp_path)
    _fixture_recreate = tmp_path / "runs/dsh_read_shadow/verified_summary.private.json"
    summary = json.loads(_fixture_recreate.read_text())
    summary["code_sha"] = "b" * 40
    _fixture_recreate.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="wrong frozen source"):
        judge(tmp_path)


def test_paired_verifier_rejects_bad_gate_or_budget_denominator(tmp_path):
    _fixture(tmp_path)
    p = tmp_path / "runs/dsh_read_down/verified_summary.private.json"
    row = json.loads(p.read_text())
    row["gate_http_statuses"] = [200, 200]
    p.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="Shadow transport mismatch"):
        judge(tmp_path)
    row["gate_http_statuses"] = [503, 503]
    p.write_text(json.dumps(row))
    ledger = tmp_path / "provider_calls.private.jsonl"
    ledger.write_text("\n".join(ledger.read_text().splitlines()[:-1]) + "\n")
    with pytest.raises(ValueError, match="global denominator mismatch"):
        judge(tmp_path)
