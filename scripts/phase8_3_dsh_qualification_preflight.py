#!/usr/bin/env python3
"""DSH Phase 8.3 native E2E readiness, OFFLINE-only and without credentials.

Reads the pinned native DSH checkout, OFF/Shadow SDK patch configs,
isolated repo-private filesystem and original global Provider request
ledger. This script NEVER accepts/reads a provider token, launches a
main-model request or copies a Hermes credential. Real DSH runs require a
future separately frozen one-shot runner with owner-controlled secure
interactive credential input and the same original physical budget.

Run: python scripts/phase8_3_dsh_qualification_preflight.py --check-offline
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml

from phase8_3_prepare_clean_home import (
    PRIVATE_ROOT, DSH_PATCHES, safe_dsh_patch, PROVIDER_ORIGIN,
)
from phase8_3_sdk_offline_preflight import (
    UPSTREAM, CLI, PIN, clean_environment, native_sdk_init,
)
from phase8_3_transport_closeout import audited_snapshot, H4

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_LEDGER = PRIVATE_ROOT / "provider_real_ledger.private.jsonl"
ORIGINAL_H3_DIGEST = (
    "5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb"
)
MODEL = "step-5-preview"
PER_RUN_CAP = 3
GLOBAL_CAP = 24
CASES = ("d1_read_off", "d2_read_shadow", "d3_runtime_down", "d4_missing_read")
EVIDENCE_MODE = "isolated-shadow-test-v1"
EVIDENCE_KEY_HEX = re.compile(r"[a-f0-9]{64}\Z")


class DshQualificationBlocked(ValueError):
    """Not eligible to launch a real DSH main Provider task."""


def _private_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or path.stat().st_mode & 0o077:
        raise DshQualificationBlocked("DSH test private directory missing or unsafe")
    if not path.resolve().is_relative_to(PRIVATE_ROOT.resolve()):
        raise DshQualificationBlocked("DSH test folder outside ignored private root")


def validate_dsh_patch(mode: str) -> dict[str, Any]:
    if mode not in {"off", "shadow"}:
        raise DshQualificationBlocked("DSH mode must be OFF or Shadow")
    patch=DSH_PATCHES / f"dsh_sdk_{mode}.yml"
    if patch.is_symlink() or not patch.is_file() or patch.stat().st_mode & 0o077:
        raise DshQualificationBlocked("DSH patch file unsafe/unavailable")
    text=patch.read_text(encoding="utf-8")
    data=yaml.safe_load(text)
    if data!=safe_dsh_patch(mode):
        raise DshQualificationBlocked("DSH patch differs from restricted source template")
    if "access_token" in text or "api_key:" in text.lower():
        raise DshQualificationBlocked("embedded API key material in patch")
    provider=data[1]["config"]["providers"]["stepfun"]
    entries=data[2]["insert"]
    if (provider["baseURL"]!=PROVIDER_ORIGIN
            or provider["apiKeyEnv"]!="STEPFUN_API_KEY"
            or provider["api"]!="openai-completions"
            or provider["retryPolicy"].get("maxRetries")!=0
            or [m["id"] for m in provider["models"]] != [MODEL]
            or len(entries)!=1
            or entries[0]["config"]["mode"]!=mode
            or entries[0]["config"].get("canary_acknowledged") is not False):
        raise DshQualificationBlocked("unapproved DSH Provider/Gate/retry configuration")
    return {
        "mode":mode,
        "provider_route":"bounded_loopback_18794",
        "credential_source":"OWNER_SUPPLIED_SEPARATE_PROCESS_ENV_ONLY",
        "provider_auto_retries":0,
        "canary_acknowledged":False,
        "patch_contains_credential":False,
    }


def check_offline() -> dict[str, Any]:
    if (PRIVATE_ROOT.is_symlink() or not PRIVATE_ROOT.is_dir()
            or PRIVATE_ROOT.stat().st_mode & 0o077):
        raise DshQualificationBlocked("private DSH test root is not restrictive")
    _private_directory(DSH_PATCHES)
    if not (UPSTREAM/"apps/cli/lib/bin.js").is_file() or CLI.is_symlink():
        raise DshQualificationBlocked("pinned native SDK entrypoint unavailable")
    try:
        actual=subprocess.check_output(
            ["git","-C",str(UPSTREAM),"rev-parse","HEAD"],
            text=True,stderr=subprocess.DEVNULL,timeout=8
        ).strip()
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired):
        raise DshQualificationBlocked("DSH native checkout not verifiable") from None
    if actual!=PIN:
        raise DshQualificationBlocked("native DSH SDK checkout SHA changed")
    plugin=ROOT/"integrations/deepseek-harness/local-system-one-dsh/dist/index.js"
    if not plugin.is_file() or plugin.is_symlink():
        raise DshQualificationBlocked("independent DSH Adapter build absent")
    summary=[validate_dsh_patch(m) for m in ("off","shadow")]
    ledger=audited_snapshot(PRIVATE_LEDGER,new_run=H4)
    if (ledger["reserved_global"]!=8 or ledger["reserved_h1"]!=3
            or ledger["reserved_h2"]!=3 or ledger["reserved_h3"]!=2
            or ledger["reserved_new"]!=0 or ledger["historic_h1_unresolved"]!=1
            or ledger["ledger_digest_sha256"]!=ORIGINAL_H3_DIGEST):
        raise DshQualificationBlocked("original 8 physical StepFun reservations changed")
    clean_subprocess=clean_environment(PRIVATE_ROOT/"dsh_offline_placeholder")
    if any(k in clean_subprocess for k in (
        "STEPFUN_API_KEY","OPENAI_API_KEY","ANTHROPIC_API_KEY",
        "HERMES_HOME","STEPFUN_BASE_URL","HTTPS_PROXY",
    )):
        raise DshQualificationBlocked("DSH SDK preflight inherits unauthorized credentials")
    pinnedsha=subprocess.check_output(["git","rev-parse","HEAD"],
                                     cwd=ROOT,text=True,timeout=8).strip()
    dirty=bool(subprocess.check_output(["git","status","--porcelain"],
                      cwd=ROOT,text=True,timeout=8).strip())
    return {
        "schema":"local-system-one/phase8_3-dsh-offline-qualification-v1",
        "sdk_source_revision":PIN,
        "candidate_source_sha":pinnedsha,
        "candidate_source_clean":not dirty,
        "platform":"deepseek_harness",
        "modes":summary,
        "real_provider_request_start_authorized":False,
        "real_native_execution_status":"NOT_RUN",
        "real_native_sdk_credential_stage":"OWNER_SECURE_INTERACTIVE_INPUT_NOT_PROVISIONED",
        "provider_token_accessed":False,
        "production_agent_credentials_accessed":False,
        "source_credential_transfer_from_hermes":False,
        "outbound_real_model_requests":0,
        "previous_physical_global_requests":ledger["reserved_global"],
        "remaining_numerical_budget_slots":GLOBAL_CAP-ledger["reserved_global"],
        "actual_subscription_credit_spend":"UNKNOWN",
        "historical_H1_provider_unresolved":1,
        "historical_overall_integrity":"BLOCKED_HISTORICAL_H1_REQUEST",
        "safe_offline_sdk_bootstrap":"AVAILABLE_WITHOUT_CREDENTIAL",
        "next_required_step":"OWNER_SUPPORTED_SECURE_DSH_KEY_PROMPT_AND_ONE_SHOT_CAP_PROXY",
        "active_authority":"NOT_AUTHORIZED",
    }


def secure_child_environment(
    home: Path, *, manually_entered_value: str, hmac_key_hex: str,
    inherited: dict[str,str] | None=None,
) -> dict[str,str]:
    """One future DSH child process, no file-based credentials.

    Must be called only AFTER the operator has entered a credential in a
    real interactive private terminal, and AFTER the future one-shot
    native runner independently attests to the LIVE 24/3 Provider proxy.
    This helper makes NO network request and never prints its env values.
    """
    if (home.is_symlink() or not home.is_dir() or
            not home.resolve().is_relative_to(PRIVATE_ROOT.resolve()) or
            home.resolve()==PRIVATE_ROOT.resolve() or
            (home.stat().st_mode & 0o077)):
        raise DshQualificationBlocked("DSH process HOME must be a private isolated directory")
    if (not isinstance(manually_entered_value,str)
            or not 12<=len(manually_entered_value)<=512
            or any(c.isspace() or ord(c)<33 or ord(c)>126
                   for c in manually_entered_value)):
        raise DshQualificationBlocked("manually entered Provider credential malformed")
    if not isinstance(hmac_key_hex,str) or not EVIDENCE_KEY_HEX.fullmatch(hmac_key_hex):
        raise DshQualificationBlocked("test-only HMAC reference key malformed")
    base=clean_environment(home,parent=inherited or {})
    base.update({
        "STEPFUN_API_KEY":manually_entered_value,
        "LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE":EVIDENCE_MODE,
        "LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX":hmac_key_hex,
        "LOCAL_SYSTEM_ONE_EVIDENCE_PRIVATE_ROOT":str(PRIVATE_ROOT),
    })
    return base


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check-offline",action="store_true",
                   help="Zero Provider calls, no credential input, no native task")
    args=p.parse_args()
    if not args.check_offline:
        p.error("only --check-offline is supported; real Provider launch is NOT available")
    try:
        print(json.dumps(check_offline(),sort_keys=True,indent=2))
    except (DshQualificationBlocked,ValueError,TypeError,OSError) as exc:
        print(json.dumps({
            "status":"BLOCKED",
            "reason_class":type(exc).__name__,
            "real_provider_requests":0,
            "active_authority":"NOT_AUTHORIZED",
        },sort_keys=True))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
