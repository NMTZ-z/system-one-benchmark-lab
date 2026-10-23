"""H2 real native Agent test-launch safety, offline only."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h2 as h2
from phase8_3_transport_closeout import audited_snapshot


def test_h2_only_read_only_and_reuses_h1_physical_ledger():
    assert h2.RUN_ID=="h2_read_shadow"
    assert h2.H2_NATIVE_TIMEOUT==90
    assert h2.PER_CASE_MAX==3
    assert h2.PHYSICAL_GLOBAL_MAX==24
    assert set(h2.ALLOWED_PORTS)=={18782,18793,18794}
    assert h2.MODEL_PATH.name==h2.MODEL_REVISION
    src=Path(h2.__file__).read_text()
    assert '"--total-cap",str(PHYSICAL_GLOBAL_MAX)' in src
    assert '"--per-run-cap",str(PER_CASE_MAX)' in src
    assert '"--execute-real-provider"' in src
    assert '"--authorize-existing-step-plan"' in src
    assert '"--scenario","read_nonce"' in src
    assert '"--mode","shadow"' in src
    assert "PRIVATE/\"provider_real_ledger.private.jsonl\"" in src
    assert '"--private-ledger",str(PRIVATE/"provider_real_ledger.private.jsonl")' in src


def test_bogus_frozen_commit_cannot_launch_any_real_task():
    with pytest.raises(h2.H2Blocked,match="pinned clean committed"):
        h2._check_setup("0"*40)


def test_unverified_H2_shadow_mode_cannot_launch(monkeypatch,tmp_path):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(h2,"PRIVATE",tmp_path)
    monkeypatch.setattr("phase8_3_real_hermes_pilot.PRIVATE",tmp_path)
    sha=h2._git("rev-parse","HEAD")
    prev=h2._git
    monkeypatch.setattr(h2,"_git",lambda *args: "" if args[:1]==("status",) else prev(*args))
    monkeypatch.setattr(h2,"auth_inspect",lambda official_auth: {
        "mode":"off","credential_stage_ready":True})
    monkeypatch.setattr(h2,"route_inspect",lambda:{"route_status":"PINNED_PROXY"})
    with pytest.raises(h2.H2Blocked,match="must be Shadow"):
        h2._check_setup(sha)


def test_new_launcher_env_cannot_inherit_any_provider_token(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY","NEVER_USE_OLD_CREDENTIAL")
    monkeypatch.setenv("OPENAI_API_KEY","ALSO_NEVER")
    monkeypatch.setenv("HERMES_HOME","/production")
    monkeypatch.setenv("STEPFUN_BASE_URL","https://api.stepfun.com/v1")
    result=h2._base_env()
    assert "STEPFUN_API_KEY" not in result
    assert "OPENAI_API_KEY" not in result
    assert "HERMES_HOME" not in result
    assert "STEPFUN_BASE_URL" not in result
    assert "NEVER_USE_OLD_CREDENTIAL" not in str(result)


def test_no_native_task_when_original_H1_ledger_is_tampered(tmp_path,monkeypatch):
    monkeypatch.setattr(h2,"PRIVATE",tmp_path)
    monkeypatch.setattr(h2,"auth_inspect",lambda official_auth:{
        "mode":"shadow","credential_stage_ready":True})
    monkeypatch.setattr(h2,"route_inspect",lambda:{"route_status":"PINNED_PROXY"})
    # Tampered H1 ledger is an unconditional preflight block.
    (tmp_path/"provider_real_ledger.private.jsonl").write_text('CORRUPT\n')
    sha=h2._git("rev-parse","HEAD")
    with pytest.raises(h2.H2Blocked,match="pinned clean committed"):
        h2._check_setup("0"*40)
    with pytest.raises(Exception):
        audited_snapshot(tmp_path/"provider_real_ledger.private.jsonl")


def test_no_h2_overwrite_in_source_or_private_run_directory():
    src=Path(h2.__file__).read_text()
    assert '"refusing H2 evidence overwrite"' in src
    assert 'H2 has already been attempted or contains preexisting logs' in src
    assert 'H1_ORIGINAL_SHA256' in src
    assert 'drain_run(' in src
    assert 'overall_phase_8_3a_integrity' in src
    assert 'BLOCKED_HISTORICAL_H1_UNRESOLVED' in src
    assert 'NOT_AUTHORIZED' in src



def test_local_real_mlx_runtime_launches_executable_entrypoint():
    source=Path(h2.__file__).read_text()
    assert 'py,"-m","local_system_one",' in source
    assert 'py,"-m","local_system_one.cli",' not in source


def test_hermes_h2_strict_two_native_events_match_their_HMAC_http_calls(monkeypatch,tmp_path):
    """Invoke real 8.2B correlation code on synthetic isolated SQLite rows."""
    import sqlite3
    from phase8_2b_native_correlate import ref
    key=b"\x59"*32
    session="SYNTHETIC_H2_SESSION_NEVER_REAL"
    callid="SYNTHETIC_H2_CALL_NEVER_REAL"
    request_tool="h2_tool_request"
    request_end="h2_turn_end_request"
    db_path=tmp_path/"state.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            "CREATE TABLE sessions(id TEXT,end_reason TEXT);"
            "CREATE TABLE messages(session_id TEXT,role TEXT,tool_call_id TEXT);"
        )
        db.execute("INSERT INTO sessions VALUES (?,?)",(session,"agent_close"))
        db.execute("INSERT INTO messages VALUES (?,?,?)",(session,"user",None))
        db.execute("INSERT INTO messages VALUES (?,?,?)",(session,"tool",callid))
    home=tmp_path
    monkeypatch.setattr(h2,"TEST_HOME",home)
    adapter=[
        {"gate":"completion","native_stage":"tool_result",
         "session_ref":ref(key,"session",session),
         "decision_request_ref":ref(key,"decision_request",request_tool),
         "tool_call_ref":ref(key,"tool_call",session+"\0"+callid)},
        {"gate":"completion","native_stage":"turn_end",
         "session_ref":ref(key,"session",session),
         "decision_request_ref":ref(key,"decision_request",request_end)},
    ]
    monkeypatch.setattr(h2,"_plugin_observations",lambda:adapter)
    http=[
        {"decision_request_ref":ref(key,"decision_request",rid),
         "http_status":200,"backend":"mlx","response_matches_request_id":True}
        for rid in (request_tool,request_end)
    ]
    report=h2._native_http_correlate(key,http)
    assert report["status"]=="PASS"
    assert report["native_http_pairs_verified"]==2
    assert report["adapter_completion_observations"]==2
    assert session not in str(report) and callid not in str(report)
    report=h2._native_http_correlate(key,http[:-1])
    assert report["status"]!="PASS"


def test_H2_model_policy_advisory_even_if_model_succeeds():
    source=Path(h2.__file__).read_text()
    assert '"native_action_changed_by_system_one":False' in source
    assert ' "active_authority":"NOT_AUTHORIZED"' in source
    assert ' "phase8_3a_overall":"BLOCKED_HISTORICAL_H1_UNRESOLVED"' in source
    assert ' "real_agent_savings":"NOT_MEASURED"' in source
    assert ' _stop_group(' in source
