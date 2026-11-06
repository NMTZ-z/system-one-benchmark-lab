"""Run an authenticated MCP decision on the verified local model, offline."""

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys

from mcp import Client

from local_system_one import mcp_server
from local_system_one.client import LocalSystemOneClient


ROOT = Path(os.environ["LOCAL_SYSTEM_ONE_HERMES_ROOT"]).resolve()
PROFILE = "mlx"
assert (ROOT / ".local-system-one-isolated-test").is_file()
assert (ROOT / "profiles" / PROFILE).is_dir()


def command(*args, timeout=150):
    return subprocess.run([sys.executable, "-m", "local_system_one", *args],
                          capture_output=True, text=True, timeout=timeout)


def child(port):
    try:
        started = command("start", "--profile", PROFILE, "--port", str(port))
        assert started.returncode == 0, started.stdout[-1000:] + started.stderr[-1000:]
        token = Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE / "access-token"
        mcp_server.client = LocalSystemOneClient(f"http://127.0.0.1:{port}", auth_token_file=token, timeout=15)

        async def call():
            async with Client(mcp_server.mcp) as client:
                result = await client.call_tool("search_gate", {
                    "task": "Explain how a reservoir stores water for later use.", "request_id": "local-mlx-mcp",
                })
                assert not result.is_error, result
                decision = result.structured_content
                assert decision["request_id"] == "local-mlx-mcp"
                assert decision["decision_source"] == "model" and decision["backend"] == "mlx", decision
                print("PASS: authenticated MCP Search decision used real local MLX inference")

        asyncio.run(call())
    finally:
        stopped = command("stop", "--profile", PROFILE, "--confirm-clients", timeout=30)
        assert stopped.returncode == 0, stopped.stdout[-1000:] + stopped.stderr[-1000:]
        assert not (Path(os.environ["LOCAL_SYSTEM_ONE_STATE_HOME"]) / "profiles" / PROFILE / "access-token").exists()


def run():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    policy = ('(version 1)(allow default)(deny network-outbound)'
              f'(allow network-outbound (remote ip "localhost:{port}"))')
    try:
        result = subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, sys.executable, __file__, "child", str(port)],
                                capture_output=True, text=True, timeout=210)
        if result.returncode:
            print(result.stderr[-5000:], file=sys.stderr)
        assert result.returncode == 0, result.stdout
        print(result.stdout.strip())
    finally:
        subprocess.run(["/usr/bin/sandbox-exec", "-p", policy, sys.executable, "-m", "local_system_one",
                        "stop", "--profile", PROFILE, "--confirm-clients"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


if __name__ == "__main__":
    child(int(sys.argv[2])) if len(sys.argv) == 3 and sys.argv[1] == "child" else run()
