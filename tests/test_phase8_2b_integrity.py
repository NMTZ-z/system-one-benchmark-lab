"""Platform-neutral, offline synthetic verification tests. No Agent/Provider traffic."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from local_system_one.evidence_integrity import (
    CAPABILITIES, EvidenceError, SCHEMA, opaque_ref, verify_evidence,
)
from local_system_one.budget_observability import BudgetError, reconcile_budget

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_provider_cap import BudgetLedger
from phase8_2b_verify import BUNDLE_SCHEMA, read_bundle, verify_bundle


def ref(*segments: str) -> str:
    return hashlib.sha256(":".join(segments).encode()).hexdigest()[:32]


def synthetic_run(platform: str, mode: str, number: int = 1) -> dict:
    """Deterministic fake IDs intentionally lack private production identity."""
    run_id = f"fixture_{platform}_{mode}_{number}"
    scope = {
        "session": ref(run_id, "session"), "turn": ref(run_id, "turn"),
        "tool_call": ref(run_id, "tool"),
    }
    events = []

    def add(kind: str, stage: str, parent: dict | None, *, extra=None, refs=None):
        event = {
            "schema": SCHEMA, "event_ref": ref(run_id, kind, stage),
            "parent_ref": parent["event_ref"] if parent else None,
            "run_id": run_id, "platform": platform, "kind": kind,
            "stage": stage, "refs": {**scope, **(refs or {})},
            "evidence_source": (
                "independently_verified" if kind == "independent_verification"
                else "platform_reported" if kind in {"adapter_observation", "decision_request", "shadow_outcome"}
                else "native_observed"
            ), "evidence_status": "verified",
        }
        event.update(extra or {})
        events.append(event)
        return event

    call = add("native_event", "tool_call", None)
    result = add("native_event", "tool_result", None)
    finish = add("native_event", "turn_end", None)
    if mode != "off":
        adapter = add("adapter_observation", "tool_result", result, extra={"gate": "completion"})
        request = add("decision_request", "request_sent", adapter,
                      refs={"decision_request": ref(run_id, "request")},
                      extra={"gate": "completion"})
        if mode == "shadow_healthy":
            decision = add("runtime_decision", "response_received", request,
                           refs={"decision_request": ref(run_id, "request")},
                           extra={"gate": "completion", "decision_source": "rule",
                                  "execution_backend": "rule", "guarded_recommendation": "verify"})
            add("shadow_outcome", "observation_done", decision,
                refs={"decision_request": ref(run_id, "request")},
                extra={"gate": "completion", "adapter_action_status": "observed"})
        else:
            add("shadow_outcome", "runtime_unavailable", request,
                refs={"decision_request": ref(run_id, "request")},
                extra={"gate": "completion", "adapter_action_status": "failed_open"})
    agent = add("agent_execution", "turn_closed", finish, extra={"outcome": "pass"})
    add("independent_verification", "verifier_done", agent, extra={"outcome": "pass"})
    return {
        "run_id": run_id, "platform": platform, "mode": mode, "task_case": "fixture_file_read",
        "events": list(reversed(events)),  # Deliberately out of order
        "capabilities": {k: {"status": "supported", "source": "synthetic_fixture"} for k in CAPABILITIES},
    }


def budget_records(run_id: str, n: int = 3) -> list[dict]:
    events = []
    for slot in range(1, n + 1):
        events += [
            {"kind": "reserved", "run": run_id, "slot": slot},
            {"kind": "attempted", "run": run_id, "slot": slot},
            {"kind": "responded", "run": run_id, "slot": slot, "http_status": 200},
            {"kind": "result", "run": run_id, "slot": slot, "http_status": 200, "duration_ms": 1.25},
        ]
    return events


def synthetic_bundle() -> dict:
    runs = [synthetic_run(platform, mode)
            for platform in ("hermes", "deepseek_harness", "contract_only")
            for mode in ("off", "shadow_healthy", "shadow_runtime_down")]
    budgets = [
        {"run_id": run["run_id"], "records": budget_records(run["run_id"]),
         "per_run_cap": 3, "total_cap": 3, "agent_reported_calls": 2,
         "decision_calls": {"gate_requests": 0 if run["mode"] == "off" else 1,
                            "rule_decisions": int(run["mode"] == "shadow_healthy"),
                            "model_inferences": 0, "failed_or_timed_out": int(run["mode"] == "shadow_runtime_down")},
         "usage_records": [], "controlled_egress_verified": True}
        for run in runs
    ]
    return {"schema": BUNDLE_SCHEMA, "runs": runs, "budgets": budgets}


@pytest.mark.parametrize("platform", ["hermes", "deepseek_harness", "contract_only"])
@pytest.mark.parametrize("mode", ["off", "shadow_healthy", "shadow_runtime_down"])
def test_contract_is_not_platform_conditional(platform, mode):
    answer = verify_evidence(synthetic_run(platform, mode))
    assert answer["evidence_integrity"] == "PASS"
    assert answer["task_outcome"] == answer["agent_execution_outcome"] == "PASS"


def test_two_overlapping_sessions_and_turns_share_one_run_without_cross_join():
    run = synthetic_run("contract_only", "shadow_healthy", 1)
    extra = synthetic_run("contract_only", "shadow_healthy", 2)
    for event in extra["events"]:
        event["run_id"] = run["run_id"]
    run["events"].extend(extra["events"])
    answer = verify_evidence(run)
    assert answer["evidence_integrity"] == "PASS"
    assert answer["event_counts"]["independent_verification"] == 2


def test_claimed_identity_must_be_present_in_each_event():
    run = synthetic_run("contract_only", "shadow_healthy")
    run["events"][0]["refs"].pop("turn")
    answer = verify_evidence(run)
    assert answer["evidence_integrity"] == "PARTIAL"
    assert "declared_turn_identity_missing" in answer["partial_reasons"]


def test_explicit_parent_survives_out_of_order_and_late_response():
    run = synthetic_run("contract_only", "shadow_healthy")
    runtime = next(x for x in run["events"] if x["kind"] == "runtime_decision")
    runtime["ts_unix_ms"] = 1760000000000
    end = next(x for x in run["events"] if x["stage"] == "turn_end")
    end["ts_unix_ms"] = 1750000000000
    assert verify_evidence(run)["evidence_integrity"] == "PASS"


@pytest.mark.parametrize("mutation,issue", [
    ("duplicate", "duplicate_event_ref"),
    ("orphan", "orphan_parent"),
    ("cross_turn", "cross_turn_link"),
    ("cross_session", "cross_session_link"),
    ("cross_request", "decision_request_identity_conflict"),
    ("cycle", "invalid_causal_edge"),
    ("duplicated_tool", "duplicate_native_tool_stage"),
])
def test_bad_links_block(mutation, issue):
    run = synthetic_run("hermes", "shadow_healthy")
    req = next(x for x in run["events"] if x["kind"] == "decision_request")
    adapter = next(x for x in run["events"] if x["kind"] == "adapter_observation")
    runtime = next(x for x in run["events"] if x["kind"] == "runtime_decision")
    if mutation == "duplicate":
        run["events"].append(deepcopy(req))
    elif mutation == "orphan":
        req["parent_ref"] = ref("nonexistent")
    elif mutation == "cross_turn":
        req["refs"]["turn"] = ref("unrelated_turn")
    elif mutation == "cross_session":
        adapter["refs"]["session"] = ref("other_session")
    elif mutation == "cross_request":
        runtime["refs"]["decision_request"] = ref("another_request")
    elif mutation == "cycle":
        adapter["parent_ref"] = req["event_ref"]
    elif mutation == "duplicated_tool":
        run["events"].append({**run["events"][-1], "event_ref": ref("newtool"),
                              "stage": "tool_call"})
    assert issue in verify_evidence(run)["issues"]


def test_missing_identity_and_unsupported_capability_are_partial():
    run = synthetic_run("deepseek_harness", "shadow_healthy")
    run["events"] = [e for e in run["events"] if e["kind"] != "adapter_observation"]
    report = verify_evidence(run)
    assert report["evidence_integrity"] == "BLOCKED"  # Orphan concrete parent, not guessed away.
    run = synthetic_run("deepseek_harness", "off")
    run["capabilities"]["model_usage_reporting"] = {"status": "unsupported", "source": "platform_audit"}
    report = verify_evidence(run)
    assert report["evidence_integrity"] == "PARTIAL"
    assert "model_usage_reporting" in report["coverage_gaps"]


def test_privacy_and_type_firewall():
    run = synthetic_run("hermes", "off")
    run["events"][0]["user_prompt"] = "DO_NOT_STORE"
    with pytest.raises(EvidenceError):
        verify_evidence(run)
    run = synthetic_run("hermes", "off")
    run["events"][0]["refs"]["session"] = "real-private-session"
    with pytest.raises(EvidenceError):
        verify_evidence(run)
    assert opaque_ref(b"a" * 32, "session", "secret") != opaque_ref(b"b" * 32, "session", "secret")
    assert opaque_ref(b"a" * 32, "session", "secret") != opaque_ref(b"a" * 32, "turn", "secret")


def test_model_reported_task_completion_is_not_external_verification():
    run = synthetic_run("contract_only", "off")
    result = next(x for x in run["events"] if x["kind"] == "independent_verification")
    result["evidence_source"] = "model_reported"
    report = verify_evidence(run)
    assert report["task_outcome"] == "UNKNOWN"
    assert report["evidence_integrity"] == "PARTIAL"


def test_budget_3_attempts_2_agent_calls_and_missing_usage():
    run = "hermes_test"
    outcome = reconcile_budget(budget_records(run), run_id=run, per_run_cap=3, total_cap=3,
                               agent_reported_calls=2, controlled_egress_verified=True)
    assert outcome["reserved_run"] == outcome["proxy_attempts"] == 3
    assert outcome["unattributed_requests"] == 1
    assert outcome["unknown_usage_requests"] == 3
    assert outcome["provider_responded"] == 3
    assert outcome["confirmed_cost"] is None


def test_budget_unknown_transport_result_and_legacy():
    run = "unknown"
    entries = [
        {"kind": "reserved", "run": run, "slot": 1},
        {"kind": "attempted", "run": run, "slot": 1},
        {"kind": "outcome_unknown", "run": run, "slot": 1},
        {"kind": "result", "run": run, "slot": 1, "http_status": 502},
    ]
    response = reconcile_budget(entries, run_id=run, per_run_cap=1, total_cap=1,
                                agent_reported_calls=None, controlled_egress_verified=True)
    assert response["provider_responded"] == 0
    assert response["outcome_unknown"] == 1
    assert response["budget_integrity"] == "PARTIAL"
    old = [entries[0], entries[-1]]
    legacy = reconcile_budget(old, run_id=run, per_run_cap=1, total_cap=1,
                              agent_reported_calls=1, controlled_egress_verified=True)
    assert legacy["proxy_attempts"] is None
    assert legacy["legacy_8_2a_counts_only"]


@pytest.mark.parametrize("tamper,issue", [
    ("overspend", "per_run_cap_exceeded"),
    ("duplicate", "duplicate_reservation"),
    ("orphan", "orphan_or_cross_run_ledger_event"),
    ("double_terminal", "multiple_terminal_outcomes"),
    ("missing_egress", "uncontrolled_or_unverified_egress"),
])
def test_budget_faults_fail_closed(tamper, issue):
    records = budget_records("example")
    controlled = True
    if tamper == "overspend":
        records += budget_records("example", 4)[-4:]
    elif tamper == "duplicate":
        records.append(deepcopy(records[0]))
    elif tamper == "orphan":
        records.append({"kind": "attempted", "run": "example", "slot": 99})
    elif tamper == "double_terminal":
        records.insert(3, {"kind": "outcome_unknown", "run": "example", "slot": 1})
    elif tamper == "missing_egress":
        controlled = False
    response = reconcile_budget(records, run_id="example", per_run_cap=3, total_cap=3,
                                agent_reported_calls=2, controlled_egress_verified=controlled)
    assert response["budget_integrity"] == "BLOCKED"
    assert issue in response["issues"]


def test_budget_does_not_infer_invoice_from_provider_usage():
    run = "example"
    with pytest.raises(BudgetError):
        reconcile_budget(budget_records(run), run_id=run, per_run_cap=3, total_cap=3,
                         agent_reported_calls=2, controlled_egress_verified=True,
                         usage_records=[{"slot": 1, "source": "provider_reported",
                                         "input_tokens": 2, "output_tokens": 4, "cost": -1}])
    result = reconcile_budget(budget_records(run), run_id=run, per_run_cap=3, total_cap=3,
                              agent_reported_calls=2, controlled_egress_verified=True,
                              usage_records=[{"slot": 1, "source": "provider_reported",
                                              "input_tokens": 2, "output_tokens": 4}])
    assert result["confirmed_cost"] is None
    assert result["unknown_usage_requests"] == 2


def test_global_ledger_fcntl_concurrency(tmp_path):
    from threading import Thread
    ledger = BudgetLedger(tmp_path / "events.jsonl", total_limit=4, per_run_limit=4)
    with ThreadPoolExecutor(max_workers=24) as pool:
        slots = list(pool.map(lambda _: ledger.reserve("race"), range(40)))
    assert sorted(x for x in slots if x is not None) == [1, 2, 3, 4]
    assert ledger.counts("race") == (4, 4)


def test_bundle_three_platforms_and_jsonl(tmp_path):
    original = synthetic_bundle()
    report = verify_bundle(original)
    assert report["cross_platform_contract"] == "PASS"
    assert len(report["run_comparisons"]) == 3
    assert all(c["status"] == "COMPLETE" for c in report["run_comparisons"].values())
    assert all(b["unattributed_requests"] == 1 for b in report["budget_reconciliation"])
    path = tmp_path / "synthetic.jsonl"
    with path.open("w", encoding="utf-8") as output:
        for run in original["runs"]:
            output.write(json.dumps({"record_type": "run", "data": run}) + "\n")
        for budget in original["budgets"]:
            output.write(json.dumps({"record_type": "budget", "data": budget}) + "\n")
    assert verify_bundle(read_bundle(path)) == report
