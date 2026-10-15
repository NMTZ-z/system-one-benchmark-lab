"""Phase 8C isolated real-MLX HTTP transport probes for both adapters.

This replays synthetic lifecycle events. It DOES NOT execute a genuine
provider-backed native Agent task or give recovery execution authority.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.router import DecisionRouter, RouterConfig
from local_system_one.runtime import MLXRuntime
from local_system_one.service import create_server

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tests"))
from test_hermes_system_one_plugin import FakeContext, load_plugin  # noqa: E402


def post(base, payload):
    request=Request(
        f"{base}/v1/workflows/retry-escalation-gate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type":"application/json"}, method="POST",
    )
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    args=parser.parse_args()

    engine=DecisionEngine(
        mlx=MLXRuntime(args.source),ane=None,
        router=DecisionRouter(RouterConfig()),
        health=ANEHealthGate(available=False),
    )
    server=create_server(engine,host="127.0.0.1",port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f"http://127.0.0.1:{server.server_address[1]}"
    try:
        sample_file=ROOT/"benchmarks/retry/calibration.jsonl"
        samples=[json.loads(line) for line in sample_file.read_text().splitlines()]
        verify=next(item for item in samples if item["gold"]=="verify_state")
        model=next(item for item in samples if item["gold"]=="retry_same")
        rule_response=post(base,verify["payload"])
        if rule_response["decision"]!="verify_state" or rule_response["backend"]!="rule":
            raise AssertionError("hard verification must bypass Laya")
        model_response=post(base,dict(model["payload"],backend="mlx"))
        if model_response["decision_source"]!="model" or model_response["backend"]!="mlx":
            raise AssertionError("actual MLX model inference not exercised")

        plugin=load_plugin()
        ctx=FakeContext(
            "shadow",service_url=base,timeout_ms=2500,
            search_gate_enabled=False,model_tier_gate_enabled=False,
            notification_gate_enabled=False,completion_gate_enabled=False,
            retry_escalation_gate_enabled=True,
        )
        plugin.register(ctx)
        start=time.perf_counter()
        returned=ctx.hooks["post_tool_call"](
            turn_id="test-isolated-1",session_id="isolated-retry",
            tool_call_id="write-a",function_name="write_file",
            status="error",error_type="TimeoutError",
            result="Private in-memory test result MUST NOT leave hook",
            function_args={"content":"Private in-memory test argument"},
            error_message="Private in-memory test exception",
        )
        callback_ms=(time.perf_counter()-start)*1000
        if returned is not None:
            raise AssertionError("Hermes hook must be advisory-only")
        observed=None
        for _ in range(100):
            observed=ctx.state.values.get("last_retry_escalation_shadow")
            if observed is not None:
                break
            time.sleep(0.02)
        if not observed or observed.get("decision")!="verify_state":
            raise AssertionError("Hermes Shadow did not observe Runtime response")
        if "Private in-memory test" in repr(ctx.state.values):
            raise AssertionError("Hermes error text entered telemetry")
        ctx.hooks["on_session_end"](session_id="isolated-retry",turn_id="test-isolated-1")

        native=subprocess.run(
            ["node",str(ROOT/"benchmarks/retry/probe_dsh.mjs"),base],
            cwd=ROOT,text=True,capture_output=True,timeout=15,check=False,
        )
        if native.returncode!=0:
            raise RuntimeError(
                "DSH isolated transport failed: "
                + native.stderr.splitlines()[-1] if native.stderr else "DSH transport failed"
            )
        dsh_result=json.loads(native.stdout.strip().splitlines()[-1])
        print(json.dumps({
            "http_rule":"PASS",
            "http_actual_mlx":"PASS",
            "http_mlx_decision":model_response["decision"],
            "hermes_adapter_http":"PASS",
            "hermes_hook_callback_ms":round(callback_ms,3),
            "dsh_adapter_http":dsh_result["dsh_loopback"],
            "backend":"mlx",
            "actual_native_provider_tasks":0,
        }))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__=="__main__":
    main()
