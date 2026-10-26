"""Non-executable read-only H4D preflight denies unsupported authority."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import stat
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import phase8_3_h4d_readiness as hr


def test_real_H4D_budget_and_authority_are_not_inferred(monkeypatch,tmp_path):
    monkeypatch.setattr(hr,"verify_frozen_git",lambda *_:{"project_frozen_commit":"a"*40,"project_git_clean":True})
    monkeypatch.setattr(hr,"validate_fixed_source_and_model",lambda *_:{"frozen_Hermes_revision":hr.HERMES_REV})
    monkeypatch.setattr(hr,"attest_historic_ledger",lambda *_:{"historic_attempts":8,"historic_one_H1_UNKNOWN_preserved":True})
    monkeypatch.setattr(hr,"stat_only_home",lambda :{"isolated_existing_test_home_mode":"off","credential_status":"NOT_VERIFIED"})
    historic_original=hr.historical_inputs
    monkeypatch.setattr(hr,"historical_inputs",lambda *_:historic_original(hr.ROOT))
    r=hr.assessment(tmp_path,"a"*40,tmp_path,tmp_path,tmp_path)
    assert r["offline_readonly_engineering_preconditions"]=="PASS_SCOPED"
    assert r["real_H4D_qualification"]=="BLOCKED_PRE_EXECUTION"
    assert r["real_H4D_run_authorized"] is False
    assert r["fresh_explicit_Provider_request_budget_approved"] is False
    assert r["real_H4D_credential_route_authorized"] is False
    assert r["new_physical_stepfun_requests"]==0
    assert r["nominal_original_24_request_unused_slots_are_NOT_authorization"] is True
    assert r["active_canary"]=="NOT_AUTHORIZED"


def test_stat_only_home_never_uses_authenticated_status(monkeypatch):
    calls=[]
    def faux(*,official_auth=True):
        calls.append(official_auth)
        return dict(mode="off",credential_status="NOT_CHECKED",credential_stage_ready=False,
                    real_provider_test_authorized_by_preflight=False,active_authority="NOT_AUTHORIZED")
    monkeypatch.setattr(hr,"inspect_test_home",faux)
    report=hr.stat_only_home()
    assert calls==[False]
    assert report["credential_file_contents_read"] is False
    assert report["credential_status"]=="NOT_VERIFIED"


@pytest.mark.parametrize("alter",[
    {"mode":"active"}, {"credential_stage_ready":True}, {"real_provider_test_authorized_by_preflight":True},
    {"credential_status":"READY"},{"active_authority":"AUTHORIZED"},
])
def test_static_check_rejects_unsafe_home(monkeypatch,alter):
    base=dict(mode="off",credential_status="NOT_CHECKED",credential_stage_ready=False,
              real_provider_test_authorized_by_preflight=False,active_authority="NOT_AUTHORIZED")
    monkeypatch.setattr(hr,"inspect_test_home",lambda **_:base|alter)
    with pytest.raises(hr.H4DReadinessBlocked,match="test_home_not_off"):
        hr.stat_only_home()


def test_original_ledger_is_hash_only_and_rejects_mutation(tmp_path,monkeypatch):
    folder=tmp_path/"private/phase8_3_native_real";folder.mkdir(parents=True)
    f=folder/"provider_real_ledger.private.jsonl";f.write_bytes(b"synthetic only")
    f.chmod(0o600)
    monkeypatch.setattr(hr,"LEDGER_SHA",hashlib.sha256(f.read_bytes()).hexdigest())
    attestation=hr.attest_historic_ledger(f)
    assert attestation["raw_ledger_rows_read"] is False
    assert attestation["historic_one_H1_UNKNOWN_preserved"] is True
    f.write_bytes(b"changed")
    with pytest.raises(hr.H4DReadinessBlocked,match="ledger_changed"):
        hr.attest_historic_ledger(f)
    f.chmod(0o644)
    with pytest.raises(hr.H4DReadinessBlocked,match="excessive_permissions"):
        hr.attest_historic_ledger(f)


def test_source_export_cannot_be_live_or_symlinked(tmp_path):
    source=tmp_path/"hermes";source.mkdir()
    model=tmp_path/hr.MODEL_REV;model.mkdir()
    (source/".env").write_text("synthetic")
    with pytest.raises(hr.H4DReadinessBlocked,match="export_is_live_or_secret"):
        hr.validate_fixed_source_and_model(source,model)
    (source/".env").unlink()
    with pytest.raises(hr.H4DReadinessBlocked,match="source_binding_mismatch"):
        hr.validate_fixed_source_and_model(source,model)


def test_frozen_git_cannot_admit_dirty_wrong_head(tmp_path):
    with pytest.raises(hr.H4DReadinessBlocked):
        hr.verify_frozen_git(tmp_path,"not_a_sha")
