"""Phase 8.3 real native H1 pilot safety checks, no paid network or Agent."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import phase8_3_real_hermes_pilot as pilot


def test_declared_limits_match_owner_budget_and_read_only_scenario():
    assert pilot.RUN_ID=="h1_read_off"
    assert pilot.PHYSICAL_GLOBAL_MAX==24
    assert pilot.PER_CASE_MAX==3
    assert pilot.NATIVE_TIMEOUT==90
    assert pilot.PROVIDER_PORT==18794


def test_invalid_git_candidate_never_enters_provider_gate(monkeypatch):
    with pytest.raises(pilot.PilotBlocked, match="pinned clean commit"):
        pilot.preflight("0"*40)


def test_missing_new_test_authorization_denied_before_proxy(monkeypatch,tmp_path):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(pilot,"PRIVATE",tmp_path)
    sha=pilot._git("rev-parse","HEAD")
    original_git = pilot._git
    monkeypatch.setattr(pilot, "_git",
        lambda *args: "" if args[:1] == ("status",) else original_git(*args))
    monkeypatch.setattr(pilot,"inspect",lambda official_auth:{"credential_stage_ready":False,"mode":"off"})
    monkeypatch.setattr(pilot,"inspect_route",lambda:{"route_status":"PINNED_PROXY"})
    with pytest.raises(pilot.PilotBlocked, match="credential or proxy"):
        pilot.preflight(sha)


def test_preflight_never_allows_shadow_as_off(monkeypatch,tmp_path):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(pilot,"PRIVATE",tmp_path)
    sha=pilot._git("rev-parse","HEAD")
    original_git = pilot._git
    monkeypatch.setattr(pilot, "_git",
        lambda *args: "" if args[:1] == ("status",) else original_git(*args))
    monkeypatch.setattr(pilot,"inspect",lambda official_auth:{"credential_stage_ready":True,"mode":"shadow"})
    monkeypatch.setattr(pilot,"inspect_route",lambda:{"route_status":"PINNED_PROXY"})
    with pytest.raises(pilot.PilotBlocked, match="H1 must observe native OFF"):
        pilot.preflight(sha)


def test_ledger_accounting_uses_physical_slots_and_no_secret(tmp_path,monkeypatch):
    monkeypatch.setattr(pilot,"RUN_ID","test_case")
    ledger=tmp_path/"ledger.private.jsonl"
    ledger.write_text("\n".join(json.dumps(x) for x in (
        {"kind":"reserved","run":"test_case","slot":1},
        {"kind":"attempted","run":"test_case","slot":1},
        {"kind":"responded","run":"test_case","slot":1,"http_status":200},
        {"kind":"result","run":"test_case","slot":1,"http_status":200,"duration_ms":100},
    ))+"\n")
    report=pilot._ledger_report(ledger)
    assert report["reserved"]==report["attempted"]==report["responded"]==report["terminal"]==1
    assert report["status_codes"]==[200]
    assert report["outcome_unknown"]==0
    assert "access_token" not in json.dumps(report)


@pytest.mark.parametrize("mutation",["too_many","duplicate","wrong_owner"])
def test_ledger_rejects_overcapacity_and_identity_conflicts(tmp_path,monkeypatch,mutation):
    monkeypatch.setattr(pilot,"RUN_ID","test_case")
    path=tmp_path/"ledger.jsonl"
    rows=[{"kind":"reserved","slot":i+1,"run":"test_case"} for i in range(2)]
    if mutation=="too_many":
        rows.extend({"kind":"reserved","slot":i+3,"run":"test_case"} for i in range(2))
    if mutation=="duplicate":
        rows.append({"kind":"reserved","slot":1,"run":"test_case"})
    if mutation=="wrong_owner":
        rows.append({"kind":"reserved","slot":3,"run":"other_case"})
    path.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
    with pytest.raises(pilot.PilotBlocked):
        pilot._ledger_report(path)


def test_no_native_proof_does_not_invent_agent_success(monkeypatch,tmp_path):
    monkeypatch.setattr(pilot,"PRIVATE",tmp_path)
    monkeypatch.setattr(pilot,"TEST_HOME",tmp_path)
    monkeypatch.setattr(pilot,"RUN_ID","missing")
    assert pilot._independent_native_proof()["valid"] is False


def test_real_runner_can_only_run_with_explicit_cli_acknowledgment():
    source=Path(pilot.__file__).read_text()
    assert 'a.execute_real_step_plan' in source
    assert '"--execute-real-provider"' in source
    assert '"--authorize-existing-step-plan"' in source
    assert 'skip_verification' not in source


def test_proxy_graceful_drain_waits_only_for_terminal_records(tmp_path):
    path = tmp_path / "private.jsonl"
    all_events = [
        {"kind":"reserved","run":"h1_read_off","slot":1},
        {"kind":"attempted","run":"h1_read_off","slot":1},
        {"kind":"responded","run":"h1_read_off","slot":1,"http_status":200},
        {"kind":"result","run":"h1_read_off","slot":1,"http_status":200,"duration_ms":1},
    ]
    path.write_text("\n".join(json.dumps(x) for x in all_events)+"\n")
    assert pilot._drain_completed_provider_responses(path,maximum_seconds=0)
    path.write_text("\n".join(json.dumps(x) for x in all_events[:-2])+"\n")
    assert not pilot._drain_completed_provider_responses(path,maximum_seconds=0)


def test_proxy_drain_never_allows_unbounded_wait(tmp_path):
    with pytest.raises(pilot.PilotBlocked):
        pilot._drain_completed_provider_responses(tmp_path/"empty",maximum_seconds=200)



def test_proxy_drain_never_accepts_terminal_record_without_attempt(tmp_path):
    path = tmp_path / "ledger.jsonl"
    rows = [
        {"kind":"reserved","run":pilot.RUN_ID,"slot":1},
        {"kind":"responded","run":pilot.RUN_ID,"slot":1,"http_status":200},
        {"kind":"result","run":pilot.RUN_ID,"slot":1,"http_status":200,"duration_ms":1},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows)+"\n")
    assert not pilot._drain_completed_provider_responses(path,maximum_seconds=0)
