"""Phase 8.3 native-real experiment safety invariants, OFFLINE only.

Exercises existing budget and native-correlation validators without reading
credentials or making ANY real or mocked StepFun request.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from phase8_2a_provider_cap import BudgetLedger
from phase8_2b_native_correlate import correlate, ref

CORRELATION_TEST_KEY = b"\x19" * 32


def test_eight_native_runs_each_three_physical_requests_stop_at_24(tmp_path):
    """Physical, not self-reported logical, slots are the nonrefundable budget."""
    ledger = BudgetLedger(tmp_path / "isolated-no-provider.jsonl",
                          total_limit=24, per_run_limit=3)
    run_ids = [f"phase8_3_case_{i}" for i in range(1, 9)]
    last = None
    for run in run_ids:
        for attempt in range(3):
            slot = ledger.reserve(run)
            assert slot is not None and slot != last
            last = slot
            ledger.mark(run, slot, "attempted")
            if attempt == 2:
                ledger.mark(run, slot, "outcome_unknown")
                ledger.finish(run, slot, 502, 10.0)
            else:
                ledger.mark(run, slot, "responded", 200)
                ledger.finish(run, slot, 200, 10.0)
        assert ledger.counts(run)[1] == 3
        assert ledger.reserve(run) is None  # run is hard-capped

    assert ledger.counts(run_ids[-1]) == (24, 3)
    assert ledger.reserve("unplanned_ninth") is None
    events = [json.loads(x) for x in ledger.path.read_text().splitlines()]
    assert sum(x["kind"] == "reserved" for x in events) == 24
    assert sum(x["kind"] == "attempted" for x in events) == 24
    assert sum(x["kind"] == "responded" for x in events) == 16
    assert sum(x["kind"] == "outcome_unknown" for x in events) == 8
    assert sum(x["kind"] == "result" for x in events) == 24
    assert "Authorization" not in ledger.path.read_text()
    assert "prompt" not in ledger.path.read_text()


def test_budget_corruption_refuses_new_reservation_without_reset(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.jsonl", total_limit=24, per_run_limit=3)
    assert ledger.reserve("first") == 1
    with ledger.path.open("a") as writer:
        writer.write("UNPARSEABLE_LEDGER\n")
    with pytest.raises((ValueError, json.JSONDecodeError)):
        ledger.reserve("second")
    assert ledger.path.read_text().endswith("UNPARSEABLE_LEDGER\n")


def test_native_claim_and_http_matching_by_clock_alone_cannot_pass():
    """Existing independent 8.2B verifier needs native event IDs, not time."""
    sid = "test_session"
    rid = "test_decision"
    adapter = [{
        "gate": "completion",
        "native_stage": "turn_end",
        "session_ref": ref(CORRELATION_TEST_KEY, "session", sid),
        "turn_ref": ref(CORRELATION_TEST_KEY, "turn", sid + "\x001"),
        "native_event_ref": ref(CORRELATION_TEST_KEY, "native_event",
                                sid + "\x001\x00turn_end"),
        "decision_request_ref": ref(CORRELATION_TEST_KEY, "decision_request", rid),
    }]
    fake_http = [{
        "decision_request_ref": ref(CORRELATION_TEST_KEY, "decision_request", rid),
        "response_matches_request_id": True,
        "http_status": 200,
        "ts_unix": 1790000000.0,
    }]
    native = []  # Missing real SDK native Session/Turn identity.
    result = correlate("deepseek_harness", native, adapter, fake_http, CORRELATION_TEST_KEY)
    assert result["status"] != "PASS"
    assert result["native_http_pairs_verified"] == 0


def test_unobserved_model_or_native_outcome_cannot_be_cast_as_real_pass():
    from local_system_one.evidence_integrity import verify_evidence
    src = {
        "run_id": "real_qualification_not_started",
        "platform": "deepseek_harness",
        "mode": "shadow_healthy",
        "events": [],
        "capabilities": {},
    }
    result = verify_evidence(src)
    assert result["task_outcome"] != "PASS"
    assert result["agent_execution_outcome"] != "PASS"
    assert result["evidence_integrity"] != "PASS"
