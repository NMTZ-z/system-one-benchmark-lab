#!/usr/bin/env python3
"""Zero-network gateway-independent Hermes native Agent entry reconnaissance.

Hermes v0.22.1 public CLI -z goes through the host multiplexer Gateway.
The official in-process hermes_cli.oneshot.run_oneshot remains available
and constructs the real AIAgent without connecting to that Gateway.
THIS SCRIPT ONLY INSPECTS SOURCE. It cannot launch a native task or
send a Provider request. Any future replacement run is a DISTINCT
frozen experiment requiring explicit additional one-shot authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

HERMES_ROOT=Path.home()/".hermes/hermes-agent"
OFFICIAL_PY=HERMES_ROOT/".venv/bin/python"
TEST_HOME=Path.home()/".hermes/system-one-phase83lab"
SOURCE=HERMES_ROOT/"hermes_cli/oneshot.py"
MAIN=HERMES_ROOT/"hermes_cli/main.py"


class DirectNativeBlocked(ValueError):
    pass


def audit() -> dict:
    if (HERMES_ROOT.is_symlink() or SOURCE.is_symlink() or MAIN.is_symlink()
            or not SOURCE.is_file() or not MAIN.is_file()
            or not TEST_HOME.is_dir() or TEST_HOME.is_symlink()):
        raise DirectNativeBlocked("missing safe installed native Hermes source/test Home")
    if not OFFICIAL_PY.is_file():
        raise DirectNativeBlocked("official isolated Hermes Python missing")
    code = '''
import hashlib,inspect,json,sys
from pathlib import Path
sys.path.insert(0,str(Path.home()/".hermes/hermes-agent"))
from hermes_cli.oneshot import run_oneshot,_run_agent
from hermes_cli.main import _run_oneshot_from_args
sig=inspect.signature(run_oneshot)
actual=set(sig.parameters)
src=inspect.getsource(run_oneshot)
agent=inspect.getsource(_run_agent)
route=inspect.getsource(_run_oneshot_from_args)
required={"prompt","provider","model","toolsets","usage_file"}
data={
 "real_agent_engine_entry_present":callable(run_oneshot) and required<=actual,
 "real_agent_constructs_AIAgent":"from run_agent import AIAgent" in agent,
 "direct_entry_bypasses_gateway":"connect_gateway(" not in src
     and "launch_gateway_chat(" not in src,
 "public_hermes_cli_oneshot_is_gateway_backed":
     "launch_gateway_chat(args)" in route,
}
print(json.dumps(data,sort_keys=True))
'''
    env={
        "HOME":str(Path.home()),
        "PATH":"/opt/homebrew/bin:/usr/bin:/bin",
        "HERMES_HOME":str(TEST_HOME),
        "HERMES_DISABLE_LAZY_INSTALLS":"1",
        "NO_PROXY":"127.0.0.1,localhost",
    }
    result=subprocess.run(
        [str(OFFICIAL_PY),"-c",code],
        cwd=HERMES_ROOT,env=env,
        capture_output=True,text=True,timeout=15,check=False,
    )
    if result.returncode!=0:
        raise DirectNativeBlocked("native Hermes source import or contract unavailable")
    try:
        flags=json.loads(result.stdout)
    except (ValueError,TypeError):
        raise DirectNativeBlocked("official native Hermes import result malformed") from None
    if not isinstance(flags,dict) or not all(x is True for x in flags.values()):
        raise DirectNativeBlocked("in-process Agent source is not a gateway-free equivalent")
    return {
        "schema":"local-system-one/phase8_3-direct-native-engine-source-preflight-v1",
        **flags,
        "oneshot_public_source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "gateway_cli_source_sha256":hashlib.sha256(MAIN.read_bytes()).hexdigest(),
        "actual_native_Agent_task_executed":False,
        "real_model_provider_requests":0,
        "future_H4_separate_run_authorized":False,
        "production_gateway_touched":False,
        "active_authority":"NOT_AUTHORIZED",
    }


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument("--check-offline",action="store_true")
    parsed=args.parse_args()
    if not parsed.check_offline:
        args.error("ONLY source preflight is supported, NO real native runner")
    try:
        print(json.dumps(audit(),sort_keys=True,indent=2))
    except (DirectNativeBlocked,ValueError,TypeError,OSError,subprocess.SubprocessError):
        print(json.dumps({"status":"BLOCKED","model_provider_requests":0}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
