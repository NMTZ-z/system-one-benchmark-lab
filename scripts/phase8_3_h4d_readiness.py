#!/usr/bin/env python3
"""Non-executable H4D readiness audit: NO auth reads or Provider/Agent calls.

Only pinned code/digests, public historical results, stat-only fixed test Home
OFF configuration and source provenance are inspected. This file has NO real
run entrypoint and cannot grant approval or Provider spending authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any

from phase8_3_real_value_intake import ROOT, assess_historical_data, historical_inputs
from phase8_3_verify_stock_shadow import SOURCE_HASHES, MODEL_SHA, RequalificationBlocked
from phase8_3_prepare_shared_dependency_home import inspect as inspect_test_home

LEDGER_SHA = "5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb"
MODEL_REV = "f9ab0b228f0fc0f14d873dbc99038f135c2da1b2"
HERMES_REV = "4d04303818b61bf3aa09278af48356315515965b"


class H4DReadinessBlocked(ValueError):
    """Unsafe or unproven read-only preflight prerequisite."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise H4DReadinessBlocked(reason)


def file_digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def validate_fixed_source_and_model(source: Path, model: Path) -> dict:
    require(source.is_dir() and not source.is_symlink(), "exported_Hermes_source_unavailable")
    require(all(not (source/marker).exists() and not (source/marker).is_symlink()
                for marker in (".git",".env","auth.json",".venv")),
            "export_is_live_or_secret_bearing")
    for name,hash_value in SOURCE_HASHES.items():
        f=source/name
        require(f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(source.resolve())
                and file_digest(f)==hash_value,
                "source_binding_mismatch")
    require(model.is_dir() and not model.is_symlink() and model.name==MODEL_REV,
            "missing_pinned_local_model")
    weights=model/"model.safetensors"
    require(weights.is_file() and file_digest(weights)==MODEL_SHA,
            "pinned_model_weights_changed")
    return {"frozen_Hermes_revision":HERMES_REV,"pinned_source_file_hashes_checked":len(SOURCE_HASHES),
            "local_Laya_revision":MODEL_REV,"local_model_weights_sha256":MODEL_SHA,
            "source_checkout_live_or_production":False}


def attest_historic_ledger(path: Path) -> dict:
    # Keep the file read scope at a single historical Provider ledger. This
    # audit has no reason to open an arbitrary source file or credential.
    require(path.name=="provider_real_ledger.private.jsonl" and
            path.parent.name=="phase8_3_native_real" and
            path.parent.parent.name=="private", "not_historic_provider_ledger_path")
    require(path.is_file() and not path.is_symlink(), "original_private_request_ledger_missing")
    require(stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "original_private_request_ledger_excessive_permissions")
    require(file_digest(path)==LEDGER_SHA,"original_private_ledger_changed")
    # Never parse, serialize or copy any raw ledger row, token, ID or message.
    return {"historic_ledger_sha256_unchanged":LEDGER_SHA,"raw_ledger_rows_read":False,
            "historic_attempts":8,"historic_global_physical_cap":24,
            "historic_one_H1_UNKNOWN_preserved":True}


def verify_frozen_git(repo: Path, expected_sha: str) -> dict:
    require(repo.is_dir() and not repo.is_symlink() and
            re.fullmatch(r"[a-f0-9]{40}",expected_sha) is not None,
            "invalid_repo_or_frozen_source")
    head=subprocess.run(["git","-C",str(repo),"rev-parse","HEAD"],
                        capture_output=True,text=True,timeout=8,check=False)
    dirty=subprocess.run(["git","-C",str(repo),"status","--porcelain"],
                         capture_output=True,text=True,timeout=8,check=False)
    require(head.returncode==0 and dirty.returncode==0 and
            head.stdout.strip()==expected_sha and not dirty.stdout.strip(),
            "dirty_or_wrong_frozen_experiment_source")
    return {"project_frozen_commit":expected_sha,"project_git_clean":True}


def stat_only_home() -> dict:
    # This explicitly requests OFFLINE inspection: NO call to hermes auth
    # status, NO credential-file open, NO Provider/proxy/network. The existing
    # verifier looks at nonsecret static config and credential stat metadata.
    result=inspect_test_home(official_auth=False)
    require(result["mode"]=="off" and
            result["credential_status"] in {"NOT_CHECKED","MISSING_NEW_PROFILE_LOGIN"} and
            result["credential_stage_ready"] is False and
            result["real_provider_test_authorized_by_preflight"] is False and
            result["active_authority"]=="NOT_AUTHORIZED",
            "test_home_not_off_or_static_only")
    return {"isolated_existing_test_home_mode":"off",
            "test_home_static_config_consistent":True,
            "credential_file_contents_read":False,
            "credential_status":"NOT_VERIFIED",
            "auth_provider_route_end_to_end_attested":False,
            "safe_existing_home_used_for_real_task":False}


def assessment(repo: Path, expected_sha: str, source: Path, model: Path,
               private_ledger: Path) -> dict[str,Any]:
    src=verify_frozen_git(repo,expected_sha)
    pinned=validate_fixed_source_and_model(source,model)
    ledger=attest_historic_ledger(private_ledger)
    from_phase8_3=assess_historical_data(historical_inputs(repo))
    require(from_phase8_3["provider_attempts_historical"]==8 and
            from_phase8_3["provider_outcome_unknown_historical"]==1 and
            from_phase8_3["separately_adjudicated_real_decision_gold_count"]==0,
            "historical_evidence_does_not_support_claimed_readiness")
    # Source-only OFF mode check, never executes Hermes, Laya or network.
    home=stat_only_home()
    return {
        "schema":"local-system-one/phase8_3-h4d-offline-readiness-v1",
        "checked_local_date":"2026-10-26",
        "scope":"READ_ONLY_SOURCE_LEDGER_STATIC_HOME_NO_PROVIDER",
        "offline_readonly_engineering_preconditions":"PASS_SCOPED",
        **src,**pinned,**ledger,**home,
        "native_stock_shadow_technical_qualification":"PASS_SCOPED_PREVIOUS_FROZEN_MATRIX",
        "real_H4D_credential_route_authorized":False,
        "new_physical_stepfun_requests":0,
        "new_local_laya_inferences":0,
        "fresh_explicit_Provider_request_budget_approved":False,
        "real_H4D_run_authorized":False,
        "real_H4D_qualification":"BLOCKED_PRE_EXECUTION",
        "actual_agent_cost_or_value_savings":"NOT_MEASURED",
        "active_canary":"NOT_AUTHORIZED",
        "blocking_items":[
            "Separate owner approval of exact paid StepFun model, physical request cap, time and cost/credit ceiling missing",
            "Official isolated authentication and every real Provider egress route not re-verified; credential contents deliberately unopened",
            "Fresh one-shot real H4D runner and independent task oracle require their own frozen source and admission",
            "Original H1 request without terminal result remains UNKNOWN; historical global integrity not reconciled",
            "Real independent decision-grade gold missing from H1-H3 published summaries",
        ],
        "nominal_original_24_request_unused_slots_are_NOT_authorization":True,
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--expected-sha",required=True)
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--model",required=True,type=Path)
    p.add_argument("--historical-ledger",required=True,type=Path)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    try:
        result=assessment(ROOT,args.expected_sha,args.source,args.model,args.historical_ledger)
    except (H4DReadinessBlocked,RequalificationBlocked,ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError) as e:
        print(json.dumps({"status":"BLOCKED","reason":type(e).__name__,
                          "real_H4D_run_authorized":False,"physical_provider_requests":0}))
        return 3
    if args.report:
        dest=args.report.absolute()
        expected=ROOT/"results/processed/phase8_3_h4d_offline_readiness.json"
        if dest!=expected or dest.exists() or dest.is_symlink():
            print(json.dumps({"status":"BLOCKED","reason":"unsafe_output_path"}))
            return 3
        dest.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
