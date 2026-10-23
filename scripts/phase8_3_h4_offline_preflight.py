#!/usr/bin/env python3
"""H4 native Hermes missing-file OFFLINE-only entrypoint, no StepFun calls.

A real read_file tool is invoked directly, under a clean, isolated Hermes
test profile with no main-model SDK, no Agent turn, no outbound HTTP and no
Provider key access. It proves the runtime tool's own typed JSON error but
does not invent Agent retry-hook status, native task outcome or HMAC links.
Checks the full immutable 8-physical-attempt H1/H2/H3 budget precursor.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from phase8_3_prepare_shared_dependency_home import (
    TEST_HOME, inspect as inspect_home, isolated_test_config,
)
from phase8_3_pin_stepfun_route import inspect as inspect_route
from phase8_3_transport_closeout import (
    audited_snapshot, H4, H3_ORIGINAL_SHA256,
)
from phase8_3_real_hermes_h2 import PRIVATE, ROOT

HERMES_PYTHON = Path.home() / ".hermes/hermes-agent/.venv/bin/python"
EXPECTED_NATIVE_ERROR_PREFIX = "File not found:"


class H4PreflightBlocked(ValueError):
    """H4 offline qualification cannot establish safe prerequisites."""


def prerequisites() -> dict:
    if (not PRIVATE.is_dir() or PRIVATE.is_symlink()
            or PRIVATE.stat().st_mode & 0o077):
        raise H4PreflightBlocked("private H4 root unavailable")
    for sub in ("runs","logs"):
        path=PRIVATE/sub
        if not path.is_dir() or path.is_symlink() or path.stat().st_mode & 0o077:
            raise H4PreflightBlocked("H4 private run/log roots unsafe")
    home=inspect_home(official_auth=True)
    if home["mode"]!="off" or not home["credential_stage_ready"]:
        raise H4PreflightBlocked("H4 requires an OFF authenticated dedicated Hermes Home")
    if inspect_route()["route_status"]!="PINNED_PROXY":
        raise H4PreflightBlocked("H4 manual StepFun credential route not hard-capped")
    import yaml
    if yaml.safe_load((TEST_HOME/"config.yaml").read_text())!=isolated_test_config("off"):
        raise H4PreflightBlocked("H4 background title model configuration unsafe")
    ledger=audited_snapshot(
        PRIVATE/"provider_real_ledger.private.jsonl",new_run=H4
    )
    if (ledger["reserved_global"]!=8
            or ledger["reserved_h1"]!=3
            or ledger["reserved_h2"]!=3
            or ledger["reserved_h3"]!=2
            or ledger["reserved_new"]!=0
            or ledger["historic_h1_unresolved"]!=1
            or ledger["ledger_digest_sha256"]!=H3_ORIGINAL_SHA256):
        raise H4PreflightBlocked("H1/H2/H3 original physical Provider ledger changed")
    if (PRIVATE/"runs"/H4).exists() or (PRIVATE/"runs"/H4).is_symlink():
        raise H4PreflightBlocked("H4 has already been attempted")
    return {
        "schema":"local-system-one/phase8_3-h4-offline-preflight-v1",
        "isolated_profile":"OFF",
        "manual_provider_credential_route":"PINNED_LOCALHOST_18794",
        "background_title_llm_upgrade":"DISABLED",
        "original_h1_h2_h3_ledger":"SHA256_VERIFIED_UNMODIFIED",
        "original_global_physical_slots_used":8,
        "nominal_physical_slots_remaining":16,
        "historical_H1_unresolved":1,
        "tool_negative_case":"PREDECLARED_READ_MISSING",
        "real_h4_native_Agent_task":"NOT_RUN",
        "real_provider_requests_from_this_preflight":0,
        "real_provider_execution_authorized":False,
        "native_retry_hook_status":"NOT_VERIFIED",
        "active_authority":"NOT_AUTHORIZED",
    }


def direct_native_tool_probe() -> dict:
    """Exactly one actual native Hermes file-tool invocation, no LLM/Agent.

    The random disposable file path is unique and NEVER created. All output
    is an allowlisted boolean/error-class summary. The original JSON error
    string and local absolute pathname never enter the report or logs.
    """
    status=prerequisites()
    if not HERMES_PYTHON.is_file():
        raise H4PreflightBlocked("existing official Hermes tool Python unavailable")
    path=PRIVATE / ("h4_offline_absent_" + secrets.token_hex(12) + ".txt")
    if path.exists() or path.is_symlink():
        raise H4PreflightBlocked("random negative file target unexpectedly exists")
    py=r'''
import json,sys
from pathlib import Path
# Official Hermes tool source lives outside this repository. Python -c does
# not inherit the Hermes CLI launcher's sys.path initialization.
sys.path.insert(0,str(Path.home()/".hermes/hermes-agent"))
from tools.file_tools import read_file_tool
from agent.tool_result_classification import has_failure_marker
from model_tools import _tool_result_observer_fields
target=Path(sys.argv[1])
assert target.is_absolute() and not target.exists() and not target.is_symlink()
raw=read_file_tool(str(target),task_id="h4_direct_offline_tool_probe")
try: value=json.loads(raw)
except (ValueError,TypeError):value={}
observer_status,observer_error_type,_=_tool_result_observer_fields("read_file",raw)
output={
 "native_tool":"read_file",
 "native_file_missing_before_and_after":not target.exists() and not target.is_symlink(),
 "typed_result_error_field":isinstance(value.get("error"),str) and
     value["error"].startswith("File not found:"),
 "typed_result_not_found":value.get("not_found") is True,
 "content_empty":not bool(value.get("content")),
 "tool_result_failure_marker":has_failure_marker(raw),
 "native_hook_observer_typed_status":observer_status,
 "native_hook_observer_error_type":observer_error_type,
 "model_provider_requests":0,
}
print(json.dumps(output,sort_keys=True))
if (not all(output[k] is True for k in (
 "native_file_missing_before_and_after","typed_result_error_field",
 "typed_result_not_found","content_empty","tool_result_failure_marker"))
 or observer_status!="error" or observer_error_type!="tool_error"):
 sys.exit(3)
'''
    env={
        "HOME":str(Path.home()),
        "PATH":os.environ.get("PATH","/opt/homebrew/bin:/usr/bin:/bin"),
        "HERMES_HOME":str(TEST_HOME),
        "HERMES_DISABLE_LAZY_INSTALLS":"1",
        "NO_PROXY":"127.0.0.1,localhost",
    }
    try:
        launched=subprocess.run(
            [str(HERMES_PYTHON),"-c",py,str(path)],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
            capture_output=True,text=True,timeout=18,check=False,
        )
    except (OSError,subprocess.TimeoutExpired):
        raise H4PreflightBlocked("isolated native read_file offline probe unavailable") from None
    if launched.returncode!=0:
        raise H4PreflightBlocked("native tool typed failure was not observed")
    try:
        evidence=json.loads(launched.stdout)
    except (TypeError,ValueError):
        raise H4PreflightBlocked("unexpected tool evidence, refuse unstructured result") from None
    if not isinstance(evidence,dict) or evidence.get("model_provider_requests")!=0:
        raise H4PreflightBlocked("offline native tool evidence malformed")
    status.update(evidence)
    status["H4_offline_tool_failure_structure"]="PASS_SCOPED"
    status["native_retry_hook_status"]="TYPED_ERROR_DERIVATION_VERIFIED_NOT_FULL_AGENT_HOOK"
    return status


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    x=parser.add_mutually_exclusive_group(required=True)
    x.add_argument("--check",action="store_true",
                   help="source/ledger/auth only, no provider or native tool")
    x.add_argument("--probe-tool-offline",action="store_true",
                   help="one local native read_file only, no Agent/Provider")
    args=parser.parse_args()
    try:
        answer=prerequisites() if args.check else direct_native_tool_probe()
        print(json.dumps(answer,sort_keys=True,indent=2))
    except (H4PreflightBlocked,OSError,ValueError,TypeError):
        print(json.dumps({
            "status":"BLOCKED","main_provider_calls":0,
            "active_authority":"NOT_AUTHORIZED",
        }))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
