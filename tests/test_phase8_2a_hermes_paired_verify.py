"""Synthetic independent-verifier contract tests; no Agent or StepFun calls."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_hermes_paired_verify import verify, FROZEN_SOURCE_SHA, CASES

NONCE = "P82A_NATIVE_READ_NONCE_SYNTHETIC_UNIT"


def _fixture(root: Path) -> tuple[Path, Path]:
    round_dir = root / "private_round"
    home = root / "hermes_home"
    round_dir.mkdir()
    home.mkdir()
    (round_dir / "runs").mkdir()
    (round_dir / "manifest.private.json").write_text(json.dumps({
        "code_sha": FROZEN_SOURCE_SHA, "provider_hard_cap_total": 9,
        "provider_hard_cap_per_case": 3, "cases": list(CASES),
        "no_new_paid_service": True, "source_equals_prior_real_hermes_adapter": True,
        "canonical_hermes_client": "v0.22.1+11.gd923a5e",
    }))
    db = sqlite3.connect(home / "state.db")
    db.executescript("""
        CREATE TABLE sessions (id TEXT, cwd TEXT, tool_call_count INTEGER,
          api_call_count INTEGER, billing_base_url TEXT, end_reason TEXT);
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
          role TEXT, content TEXT, tool_call_id TEXT, tool_calls TEXT,
          tool_name TEXT, timestamp INTEGER);
    """)
    for ix, case in enumerate(CASES):
        folder = round_dir / "runs" / case
        folder.mkdir()
        (folder / "input.txt").write_text(NONCE)
        statuses = [] if ix == 0 else [200, 200] if ix == 1 else [503, 503]
        backend = [] if ix == 0 else ["mlx", "mlx"] if ix == 1 else [None, None]
        d = {
            "code_sha": FROZEN_SOURCE_SHA, "run_id": case,
            "platform": "hermes", "main_model": "stepfun/step-5-preview",
            "scenario": "read_nonce", "mode": "off" if ix == 0 else "shadow",
            "process_exit_code": 0, "timed_out": False, "input_unchanged": True,
            "read_proof": {"final_answer_matches_nonce": True},
            "provider_calls_counted_at_proxy": 3, "provider_global_used": (ix + 1) * 3,
            "gate_http_statuses": statuses, "gate_backend": backend,
            "hermes_state_deltas": {"completion_shadow_history": 0 if ix == 0 else 1,
                "completion_loop_probe_history": 0 if ix == 0 else 1,
                "retry_escalation_shadow_history": 0},
            "usage": {"api_calls": 2, "completed": True},
            "elapsed_seconds": 8.0,
        }
        (folder / "verified_summary.private.json").write_text(json.dumps(d))
        session_id = "synthetic_" + case
        call_id = "test_tool_call_" + str(ix)
        db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (
            session_id, str(folder.resolve()), 1, 2, "http://127.0.0.1:18794", "agent_close"))
        rows = [
            (session_id, "user", "read the private file", None, None, None, 1),
            (session_id, "assistant", "", None, json.dumps([{
                "id": call_id, "function": {"name": "read_file"}}]), None, 2),
            (session_id, "tool", "Synthetic tool result: " + NONCE, call_id, None, "read_file", 3),
            (session_id, "assistant", "read actual content: " + NONCE, None, None, None, 4),
        ]
        db.executemany("INSERT INTO messages (session_id,role,content,tool_call_id,tool_calls,tool_name,timestamp) VALUES (?,?,?,?,?,?,?)", rows)
    db.commit()
    db.close()
    events = []
    for slot in range(1, 10):
        case = CASES[(slot - 1) // 3]
        events.extend([
            {"kind": "reserved", "slot": slot, "run": case},
            {"kind": "result", "slot": slot, "run": case, "http_status": 200},
        ])
    (round_dir / "provider_calls.private.jsonl").write_text(
        "\n".join(json.dumps(x) for x in events) + "\n")
    gate_rows = [
        {"path": "/v1/workflows/completion-gate", "http_status": 200,
         "backend": "mlx", "decision_source": "model"},
        {"path": "/v1/workflows/completion-gate", "http_status": 200,
         "backend": "mlx", "decision_source": "model"},
        {"path": "/v1/workflows/completion-gate", "http_status": 503, "backend": None},
        {"path": "/v1/workflows/completion-gate", "http_status": 503, "backend": None},
    ]
    (round_dir / "collector_events.private.jsonl").write_text(
        "\n".join(json.dumps(x) for x in gate_rows) + "\n")
    return round_dir, home


def test_synthetic_hermes_paired_fixture_accepts_only_explicit_scoped_claim(tmp_path):
    r, h = _fixture(tmp_path)
    result = verify(r, hermes_home=h)
    assert result["status"] == "SCOPED_HERMES_OFF_SHADOW_DOWN_NATIVE_PASS"
    assert result["provider_hard_cap"]["actually_reserved"] == 9
    assert result["cases"]["hermes_shadow"]["native_tool_call_result_id_paired"]
    assert result["shadow_runtime_HTTP"]["degraded_completion_503"] == 2
    assert result["active_authority"] == "NOT_AUTHORIZED"


def test_reject_hermes_native_tool_call_mismatch(tmp_path):
    r, h = _fixture(tmp_path)
    db = sqlite3.connect(h / "state.db")
    db.execute("UPDATE messages SET tool_call_id='wrong_id' WHERE role='tool' AND session_id='synthetic_hermes_off'")
    db.commit(); db.close()
    with pytest.raises(ValueError, match="call/result identity mismatch"):
        verify(r, hermes_home=h)


def test_reject_absent_tool_content_even_when_final_answer_matches(tmp_path):
    r, h = _fixture(tmp_path)
    db = sqlite3.connect(h / "state.db")
    db.execute("UPDATE messages SET content='no actual file returned' WHERE role='tool' AND session_id='synthetic_hermes_shadow'")
    db.commit(); db.close()
    with pytest.raises(ValueError, match="tool result did not return"):
        verify(r, hermes_home=h)


def test_reject_wrong_provider_gateway_or_billing_endpoint(tmp_path):
    r, h = _fixture(tmp_path)
    db = sqlite3.connect(h / "state.db")
    db.execute("UPDATE sessions SET billing_base_url='https://api.stepfun.ai/step_plan/v1' WHERE id='synthetic_hermes_down'")
    db.commit(); db.close()
    with pytest.raises(ValueError, match="loopback Provider"):
        verify(r, hermes_home=h)


def test_reject_provider_reservation_loss(tmp_path):
    r, h = _fixture(tmp_path)
    ledger = r / "provider_calls.private.jsonl"
    ledger.write_text("\n".join(ledger.read_text().splitlines()[:-1]) + "\n")
    with pytest.raises(ValueError, match="network denominator"):
        verify(r, hermes_home=h)


def test_reject_down_runtime_no_fail_open_evidence(tmp_path):
    r, h = _fixture(tmp_path)
    gate = r / "collector_events.private.jsonl"
    records = [json.loads(l) for l in gate.read_text().splitlines()]
    records[-1]["http_status"] = 200
    gate.write_text("\n".join(json.dumps(item) for item in records) + "\n")
    with pytest.raises(ValueError, match="Runtime-down Shadow did not fail-open"):
        verify(r, hermes_home=h)
