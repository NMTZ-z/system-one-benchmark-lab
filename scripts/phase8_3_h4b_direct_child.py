#!/usr/bin/env python3
"""Gateway-INDEPENDENT official Hermes in-process one-shot H4B child.

This entry must be invoked ONLY inside the OS Seatbelt sandbox prepared
by the H4B orchestrator. It uses the actual hermes_cli.oneshot.run_oneshot
and genuine run_agent.AIAgent, not a mock. All tool access is narrowed to
exactly one permitted native read_file target by:
  1. a process-local custom toolset exposing only read_file,
  2. an in-process native registry dispatch guard checking tool NAME and
     exact preregistered MISSING target PATH, and
  3. macOS Seatbelt prohibiting file writes beyond the test-only SQLite,
     plugin state and this disposable case directory and forbidding any
     nonlocal Provider egress.
No plugin/installed Hermes source files or credentials are edited.
No direct real execution exists without an explicit --run-native flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
PRIVATE=ROOT/"private/phase8_3_native_real"
CASE_ID="h4b_missing_read"
TARGET_PREFIX="h4b_absent_"
CASE_DIR=PRIVATE/"runs"/CASE_ID
TEST_HOME=Path.home()/".hermes/system-one-phase83lab"
HERMES_INSTALL=Path.home()/".hermes/hermes-agent"
HERMES_PYTHON=HERMES_INSTALL/".venv/bin/python"
CUSTOM_TOOLSET="phase83-h4b-one-read-file-only"
MODEL="step-5-preview"
PROVIDER="stepfun"


def configure_for_case(case_id: str) -> None:
    """Explicitly bind ONLY a new H4C child in its own Python process.

    The default remains original H4B. H4C may not be used as a
    convenience rerun of H4B's immutable private original.
    """
    global CASE_ID, CASE_DIR, TARGET_PREFIX, CUSTOM_TOOLSET
    if case_id!="h4c_missing_read":
        raise DirectAgentBlocked("only a new separately named H4C is eligible")
    CASE_ID=case_id
    CASE_DIR=PRIVATE/"runs"/case_id
    TARGET_PREFIX="h4c_absent_"
    CUSTOM_TOOLSET="phase83-h4c-one-read-file-only"


class DirectAgentBlocked(ValueError):
    """H4B official native Agent cannot be safely invoked."""


def check_case() -> tuple[Path,str]:
    if (CASE_DIR.is_symlink() or not CASE_DIR.is_dir()
            or CASE_DIR.name!=CASE_ID
            or CASE_DIR.stat().st_mode & 0o077
            or CASE_DIR.resolve().parent != (PRIVATE/"runs").resolve()):
        raise DirectAgentBlocked("H4B case is not a restricted disposable folder")
    if (TEST_HOME != Path.home()/".hermes/system-one-phase83lab"
            or TEST_HOME.is_symlink()
            or os.environ.get("HERMES_HOME")!=str(TEST_HOME)):
        raise DirectAgentBlocked("H4B direct native must stay in fixed isolated test Home")
    if Path.cwd().resolve()!=CASE_DIR.resolve():
        raise DirectAgentBlocked("native task cwd must be the isolated H4B case folder")
    if os.environ.get("HERMES_DISABLE_LAZY_INSTALLS")!="1":
        raise DirectAgentBlocked("installed dependency repair disabled for H4B")
    if any(os.environ.get(k) for k in (
        "OPENAI_API_KEY","ANTHROPIC_API_KEY","STEPFUN_API_KEY",
        "STEPFUN_BASE_URL","HTTPS_PROXY","HTTP_PROXY","ALL_PROXY",
    )):
        raise DirectAgentBlocked("inherited alternate Provider credentials or proxy forbidden")
    if os.environ.get("LOCAL_SYSTEM_ONE_EVIDENCE_ENABLE")!="isolated-shadow-test-v1":
        raise DirectAgentBlocked("H4B correlation mode must be on")
    hmac_key=os.environ.get("LOCAL_SYSTEM_ONE_EVIDENCE_KEY_HEX","")
    if len(hmac_key)!=64 or any(ch not in "0123456789abcdef" for ch in hmac_key):
        raise DirectAgentBlocked("H4B keyed native proof is missing")
    short=CASE_ID.split("_")[0]
    manifest=CASE_DIR/f"{short}_missing_target.private.json"
    prompt_file=CASE_DIR/f"{short}_prompt.private.txt"
    if (manifest.is_symlink() or prompt_file.is_symlink()
            or not manifest.is_file() or not prompt_file.is_file()
            or manifest.stat().st_mode & 0o077
            or prompt_file.stat().st_mode & 0o077):
        raise DirectAgentBlocked("pre-Agent private source document absent")
    data=json.loads(manifest.read_text(encoding="utf-8"))
    if set(data)!={"scenario","path","basename_sha256","was_absent_before_agent"}:
        raise DirectAgentBlocked("untrusted source manifest contract")
    target=Path(data["path"]) if isinstance(data.get("path"),str) else None
    if (target is None or target.parent!=CASE_DIR
            or target.name[:len(TARGET_PREFIX)]!=TARGET_PREFIX
            or len(target.name)!=39
            or not target.name.endswith(".txt")
            or data["scenario"]!="read_missing"
            or data["was_absent_before_agent"] is not True
            or data["basename_sha256"]!=hashlib.sha256(
                target.name.encode("utf-8")).hexdigest()
            or target.exists() or target.is_symlink()):
        raise DirectAgentBlocked("target is not exact preregistered ABSENT path")
    prompt=prompt_file.read_text(encoding="utf-8")
    if (str(target) not in prompt or "read_file" not in prompt
            or len(prompt)>1600):
        raise DirectAgentBlocked("source prompt does not identify exact native read tool")
    return target,prompt


def install_readonly_tool_guard(target: Path) -> dict:
    """A child-only toolset and immediate dispatch guard, no Agent request."""
    if not HERMES_INSTALL.is_dir() or HERMES_INSTALL.is_symlink():
        raise DirectAgentBlocked("pinned official installed Hermes source unavailable")
    sys.path.insert(0,str(HERMES_INSTALL))
    from toolsets import create_custom_toolset, resolve_toolset, validate_toolset
    create_custom_toolset(
        CUSTOM_TOOLSET,"One native read_file for isolated H4B only",
        tools=["read_file"],
    )
    if not validate_toolset(CUSTOM_TOOLSET) or resolve_toolset(CUSTOM_TOOLSET)!=["read_file"]:
        raise DirectAgentBlocked("native official toolset could authorize extra tools")
    from tools.registry import registry
    original=registry.dispatch
    def allow_exact_missing_read(name: str, args: Any, *extra, **kwargs):
        if (name!="read_file" or not isinstance(args,dict)
                or args.get("path")!=str(target)
                or set(args)-{"path","offset","limit"}):
            raise DirectAgentBlocked("native Agent attempted unapproved tool or target")
        return original(name,args,*extra,**kwargs)
    registry.dispatch=allow_exact_missing_read
    return {
        "only_advertised_native_tool":"read_file",
        "exact_absent_target_guard_installed":True,
        "disabled_other_tools":True,
        "modifies_parent_hermes_source":False,
        "main_provider_requests":0,
    }



def main() -> None:
    cmd=argparse.ArgumentParser(description=__doc__)
    action=cmd.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-offline",action="store_true")
    action.add_argument("--run-native",action="store_true")
    args=cmd.parse_args()
    try:
        target,_=check_case()
        guard=install_readonly_tool_guard(target)
        from hermes_cli.oneshot import run_oneshot, _validate_explicit_toolsets
        selected,error=_validate_explicit_toolsets([CUSTOM_TOOLSET])
        if error is not None or selected!=[CUSTOM_TOOLSET]:
            raise DirectAgentBlocked("actual in-process one-shot toolset validation failed")
        if args.check_offline:
            # Do not stop at merely importing run_oneshot: Hermes' entry
            # writes /dev/null for stdout/stderr redirection BEFORE any
            # actual AIAgent is constructed. Exercise its genuine preamble
            # with a synthetic _run_agent stub, NO main model/Provider.
            import io
            from contextlib import redirect_stdout
            import hermes_cli.oneshot as original_oneshot
            previous=original_oneshot._run_agent
            def no_model_simulator(*positional,**keywords):
                return "H4B_OFFLINE_NO_NETWORK",{
                    "completed":True,"failed":False,
                }
            output=io.StringIO()
            original_oneshot._run_agent=no_model_simulator
            try:
                with redirect_stdout(output):
                    rc=run_oneshot(
                        "H4B_SYNTHETIC_OFFLINE",
                        model=MODEL,provider=PROVIDER,
                        toolsets=[CUSTOM_TOOLSET],usage_file=None,
                    )
            finally:
                original_oneshot._run_agent=previous
            if rc!=0 or "H4B_OFFLINE_NO_NETWORK" not in output.getvalue():
                raise DirectAgentBlocked("native one-shot stdout/credential-free preamble failed")
            print(json.dumps({
                "schema":f"local-system-one/phase8_3-{CASE_ID.split('_')[0]}-direct-native-child-v1",
                **guard,
                "official_hermes_inprocess_engine_imported":callable(run_oneshot),
                "official_oneshot_preamble_zero_provider_passed":True,
                "test_Hermes_home":"fixed_isolated_only",
                "real_Agent_invoked":False,
                "active_authority":"NOT_AUTHORIZED",
            },sort_keys=True))
            return
        # Do not print or carry any Provider key in this process stdout.
        # Official run_oneshot masks low-level stdout/stderr and returns
        # only its final Agent text; the parent keeps them under private/.
        exit_code=run_oneshot(
            check_case()[1],model=MODEL,provider=PROVIDER,
            toolsets=[CUSTOM_TOOLSET],
            usage_file=str(CASE_DIR/"usage.private.json"),
        )
        # Strictly local observer-only daemon threads may need a bounded
        # follow-through to persist their Completion/Retry advisory evidence.
        # No new Agent turn, model request, file tool or Gateway is launched.
        time.sleep(3)
        raise SystemExit(exit_code if type(exit_code) is int else 3)
    except DirectAgentBlocked:
        print(json.dumps({"status":"BLOCKED_NO_PROVIDER_OR_NATIVE_TOOL_PROOF",
                          "active_authority":"NOT_AUTHORIZED"}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
