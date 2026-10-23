"""Future real H4 launcher admission, purely offline security tests."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_real_hermes_h4 as h4


def test_real_H4_exact_frozen_clean_source_gate():
    with pytest.raises(h4.H4Blocked,match="frozen clean committed"):
        h4._preflight("0"*40)


def test_real_H4_strict_context_no_live_case_reuse(tmp_path,monkeypatch):
    monkeypatch.setattr(h4,"TEST_HOME",tmp_path)
    plugin_root=tmp_path/"plugin-data"/"one"
    plugin_root.mkdir(parents=True)
    contents={
        "completion_loop_probe_history":[{"gate":"completion","mode":"shadow","ts":1}],
        "completion_shadow_history":[{"gate":"completion","mode":"shadow","ts":2}],
        "retry_escalation_shadow_history":[],
    }
    (plugin_root/"state.json").write_text(json.dumps(contents))
    initial=h4._history_snapshot()
    assert len(initial["completion_shadow_history"])==1
    assert h4._history_delta(initial)=={
        "completion_loop_probe_history":[],
        "completion_shadow_history":[],
        "retry_escalation_shadow_history":[],
    }
    contents["retry_escalation_shadow_history"].append({
        "gate":"retry_escalation","mode":"shadow","action_status":"observed",
    })
    (plugin_root/"state.json").write_text(json.dumps(contents))
    delta=h4._history_delta(initial)
    assert len(delta["retry_escalation_shadow_history"])==1
    contents["completion_shadow_history"][0]["ts"]=3
    (plugin_root/"state.json").write_text(json.dumps(contents))
    with pytest.raises(h4.H4Blocked,match="truncated/changed"):
        h4._history_delta(initial)


@pytest.mark.parametrize("run_key",[
    "runtime","observer","provider",
])
def test_separate_H4_local_services_have_distinct_bound_loopback_ports(run_key):
    assert {h4.RUNTIME_PORT,h4.OBSERVER_PORT,h4.PROVIDER_PORT}=={
        18782,18793,18794}
    code=Path(h4.__file__).read_text()
    assert '127.0.0.1' in code
    assert 'PRIVATE/"provider_real_ledger.private.jsonl"' in code
    assert '"--total-cap",str(PHYSICAL_GLOBAL_MAX)' in code
    assert '"--per-run-cap",str(PER_CASE_MAX)' in code


def test_provider_budget_hard_cap_and_no_automatic_native_retry():
    code=Path(h4.__file__).read_text()
    assert '"--execute-real-provider"' in code
    assert '"--authorize-existing-step-plan"' in code
    assert '"--scenario","read_missing"' in code
    assert '"--timeout",str(H4_TIMEOUT)' in code
    assert 'H3_ORIGINAL_SHA256' in code
    assert 'previous["reserved_global"]!=8' in code
    assert 'provider_calls' not in code or 'provider_credit_debit' in code
    assert h4.PHYSICAL_GLOBAL_MAX==24
    assert h4.PER_CASE_MAX==3
    assert h4.H4_TIMEOUT==90
    assert h4.RUN_ID=="h4_missing_read"
    assert "active_authority" in code and "NOT_AUTHORIZED" in code
    assert "no_auto_retry_authority" in code
    assert 'restoration=set_test_mode("off")' in code


def test_H4_plugin_replay_requires_exact_frozen_source():
    code=Path(h4.__file__).read_text()
    assert 'plugin_audit(apply=False)["new_isolated_plugin_matches_frozen_commit"]' in code
    assert 'route_inspect().get("route_status")!="PINNED_PROXY"' in code
    assert 'cfg!=isolated_test_config("shadow")' in code
    assert '"H4 is one-shot; refuse existing attempted evidence"' in code


def test_H4_retry_event_is_never_inferred_from_completion_message():
    code=Path(h4.__file__).read_text()
    assert 'verify_retry_exact(' in code
    assert '"h4_retry_observation":"PASS" if retry_pass else "NOT_VERIFIED"' in code
    assert 'check_sqlite_failed_read(' in code
    assert 'len(retries)==1' in code
    assert 'len(completion)==2' in code
    assert '"agent_final_truthfulness":"NOT_AUTOMATICALLY_VERIFIED"' in code


def test_app_enforces_real_provider_opt_in():
    code=Path(h4.__file__).read_text()
    assert '--execute-real-step-plan' in code
    assert 'not args.execute_real_step_plan' in code
    assert '_preflight(frozen_sha)' in code
    assert 'new_main_provider_requests' not in code or 'UNKNOWN_IF_ATTEMPTED' in code
