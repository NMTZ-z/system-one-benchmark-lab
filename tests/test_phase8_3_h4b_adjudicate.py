"""Pure synthetic postrun validator: no API/Agent, never consumes original H4B."""
from __future__ import annotations

from pathlib import Path
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import phase8_3_h4b_adjudicate as ver


@pytest.fixture
def fake(tmp_path,monkeypatch):
    before=tmp_path/"private"
    before.mkdir()
    case=before/"runs/h4b_missing_read"
    case.mkdir(parents=True)
    post=before/"post_state.sqlite"
    post.write_bytes(b"test")
    key=before/"hmac.bin"
    key.write_bytes(b"\x33"*32)
    key.chmod(0o600)
    monkeypatch.setattr(ver,"PRIVATE",before)
    monkeypatch.setattr(ver,"CASE_DIR",case)
    monkeypatch.setattr(ver,"POST_DB",post)
    monkeypatch.setattr(ver,"HMAC_FILE",key)
    monkeypatch.setattr(ver,"PROVIDER_LEDGER",before/"real.jsonl")
    monkeypatch.setattr(ver,"OBSERVER",before/"observer.jsonl")
    monkeypatch.setattr(ver,"FINAL_REPORT",before/"rollback.json")
    sha="a"*40
    original={
        "candidate_source_sha":sha,"run_id":ver.RUN_ID,
        "agent_platform":"official_hermes_inprocess_AIAgent",
        "native_child_exit_code":0,
        "native_child_timed_out":False,
        "error_class":None,
        "private_original_file_still_missing":True,
    }
    receipt={
        "status":"TEST_HOME_STATE_RESTORED",
        "mode":"off",
        "credential_metadata_unchanged":True,
        "sqlite_logical_snapshot_restored":True,
        "plugin_private_state_restored":True,
        "test_config_restored":True,
        "public_plugin_source_restored":True,
    }
    history={
        "reserved_global":10,"reserved_h1":3,
        "reserved_h2":3,"reserved_h3":2,
        "reserved_original_h4":0,
        "reserved_new":2,"attempted_new":2,
        "responded_new":2,"unknown_new":0,
        "finalized_new":2,
        "historic_h1_unresolved":1,
        "new_run_status":"SCOPE_COMPLETE",
        "ledger_digest_sha256":"b"*64,
    }
    oracle={
        "native_result_structured_missing_file":True,
        "tool_calls_exactly_one":True,
        "tool_call_result_identity_paired":True,
        "target_absent_before_and_after":True,
    }
    completion=[
        {"gate":"completion","mode":"shadow","native_stage":"tool_result"},
        {"gate":"completion","mode":"shadow","native_stage":"turn_end"},
    ]
    retry=[{"gate":"retry_escalation","mode":"shadow","action_status":"observed"}]
    http=[
        {"path":"/v1/workflows/completion-gate","http_status":200,
         "backend":"mlx","response_matches_request_id":True},
        {"path":"/v1/workflows/completion-gate","http_status":200,
         "backend":"mlx","response_matches_request_id":True},
        {"path":"/v1/workflows/retry-escalation-gate","http_status":200},
    ]
    f={
        "original":original,"receipt":receipt,"history":history,"oracle":oracle,
        "delta":{
            "completion_loop_probe_history":[completion[0]],
            "completion_shadow_history":[completion[1]],
            "retry_escalation_shadow_history":retry,
        },
        "http":http,
        "cjoin":{"status":"PASS","native_http_pairs_verified":2},
        "rjoin":{
            "native_retry_tool_hmac_match":True,
            "retry_http_hmac_exact_match":True,
            "no_native_retry_or_active_action_observed_from_advisor":True,
        },
    }
    monkeypatch.setattr(ver,"_read_json",lambda path: (
        f["original"] if "h4b_verified" in str(path) else f["receipt"]))
    monkeypatch.setattr(ver,"audited_snapshot",lambda *a,**kw:f["history"])
    monkeypatch.setattr(ver,"check_sqlite_failed_read",lambda *a,**kw:f["oracle"])
    monkeypatch.setattr(ver,"_adapter_history_delta",lambda:f["delta"])
    monkeypatch.setattr(ver,"_read_rows",lambda path:f["http"])
    monkeypatch.setattr(ver,"_completion_join",lambda *a,**kw:f["cjoin"])
    monkeypatch.setattr(ver,"verify_retry_exact",lambda *a,**kw:f["rjoin"])
    return sha,f


def test_native_failure_and_retry_are_independent_accepted_evidence(fake):
    sha,f=fake
    outcome=ver.adjudicate(frozen_sha=sha)
    assert outcome["H4B_scoped_verdict"]=="PASS_SCOPED"
    assert outcome["native_exactly_one_read_file"] is True
    assert outcome["native_structured_error"] is True
    assert outcome["completion_native_adapter_http_links"]==2
    assert outcome["retry_native_tool_hmac_proven"] is True
    assert outcome["isolated_test_home_reverted_to_OFF"] is True
    assert outcome["H1_original_unresolved"]==1
    assert outcome["phase8_3a_global"]=="BLOCKED_HISTORICAL_H1_UNRESOLVED"
    assert outcome["read_or_backed_up_provider_key"] is False
    assert outcome["actual_subscription_credit_debit"]=="UNKNOWN"


@pytest.mark.parametrize("mutation",[
    "no_native_tool","native_error_fake","missing_retry",
    "retry_no_provenance","bad_completion_join","no_http",
    "wrong_history","h1_forged","rollback_failed","credential_changed",
    "wrong_source","native_nonzero",
])
def test_h4b_missing_or_forged_provenance_is_never_scoped_pass(fake,mutation):
    sha,f=fake
    if mutation=="no_native_tool":f["oracle"]["tool_calls_exactly_one"]=False
    elif mutation=="native_error_fake":f["oracle"]["native_result_structured_missing_file"]=False
    elif mutation=="missing_retry":f["delta"]["retry_escalation_shadow_history"]=[]
    elif mutation=="retry_no_provenance":f["rjoin"]["native_retry_tool_hmac_match"]=False
    elif mutation=="bad_completion_join":f["cjoin"]["native_http_pairs_verified"]=1
    elif mutation=="no_http":f["http"].pop()
    elif mutation=="wrong_history":f["history"]["reserved_global"]=25
    elif mutation=="h1_forged":f["history"]["historic_h1_unresolved"]=0
    elif mutation=="rollback_failed":f["receipt"]["status"]="ROLLBACK_UNVERIFIED"
    elif mutation=="credential_changed":f["receipt"]["credential_metadata_unchanged"]=False
    elif mutation=="wrong_source":f["original"]["candidate_source_sha"]="0"*40
    elif mutation=="native_nonzero":f["original"]["native_child_exit_code"]=3
    try:
        result=ver.adjudicate(frozen_sha=sha)
        assert result["H4B_scoped_verdict"]!="PASS_SCOPED"
    except ver.AdjudicationBlocked:
        pass


def test_h4b_requires_explicit_valid_frozen_sha(fake):
    with pytest.raises(ver.AdjudicationBlocked):
        ver.adjudicate(frozen_sha="../unsafe")
