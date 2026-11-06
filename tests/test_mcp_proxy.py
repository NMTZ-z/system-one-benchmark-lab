import asyncio
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

pytest.importorskip("mcp")
from mcp import Client

from local_system_one import first_run, mcp_server
from local_system_one.client import LocalSystemOneClient
from local_system_one.service import create_server
from test_completion_gate import FakeEngine
from test_retry_escalation_gate import payload as retry_payload


def test_mcp_discovery_five_gate_parity_and_failures(tmp_path, monkeypatch):
    token, _ = first_run._access_token(tmp_path)
    server = create_server(FakeEngine(), port=0, auth_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    proxy = LocalSystemOneClient(base, auth_token_file=tmp_path / "access-token")
    monkeypatch.setattr(mcp_server, "client", proxy)
    retry = retry_payload()
    cases = [
        ("search_gate", {"task": "Rewrite provided text", "source_scope": "provided_only", "request_id": "s"}, "decision"),
        ("model_tier_gate", {"task": "Check the plan", "irreversible": True, "request_id": "m"}, "tier"),
        ("notification_gate", {"event": "A blocking failure occurred", "blocking_failure": True, "request_id": "n"}, "delivery"),
        ("completion_gate", {"task": "Finish the task", "current_result": "Incomplete", "execution_state": {"blocking_failure": True}, "request_id": "c"}, "decision"),
        ("retry_escalation_gate", retry, "guarded_decision"),
    ]

    async def exercise():
        async with Client(mcp_server.mcp) as mcp:
            listing = await mcp.list_tools()
            assert {tool.name for tool in listing.tools} == {name for name, _, _ in cases} | {"system_one_health"}
            for name, arguments, decision_key in cases:
                direct = getattr(proxy, name)(**arguments)
                result = await mcp.call_tool(name, arguments)
                assert not result.is_error
                observed = result.structured_content
                for key in ("workflow", decision_key, "decision_source", "reason", "backend", "request_id"):
                    assert observed[key] == direct[key]
                if name in ("completion_gate", "retry_escalation_gate"):
                    assert observed["advisory_only"] is True
            health = await mcp.call_tool("system_one_health", {})
            assert health.structured_content == proxy.health()
            bad = await mcp.call_tool("completion_gate", {"task": "x"})
            assert bad.is_error
            private_key = "PRIVATE_INPUT_SENTINEL"
            bad = await mcp.call_tool("completion_gate", {"task": "x", "current_result": "y", "execution_state": {private_key: True}})
            assert bad.is_error and private_key not in str(bad.model_dump())
            monkeypatch.setattr(mcp_server, "client", LocalSystemOneClient(base, auth_token="wrong"))
            denied = await mcp.call_tool("search_gate", {"task": "x"})
            assert denied.is_error and "401" in str(denied.model_dump())
            monkeypatch.setattr(mcp_server, "client", proxy)
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            down = await mcp.call_tool("search_gate", {"task": "x"})
            assert down.is_error

    try:
        asyncio.run(exercise())
    finally:
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=2)
        server.server_close()


def test_mcp_reports_overload_and_timeout(monkeypatch):
    class Unavailable(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            nonce = self.headers["X-Local-System-One-Challenge"]
            proof = hmac.new(self.server.test_token.encode(), f"identity:{nonce}:{self.connection.getsockname()[0]}:{self.connection.getsockname()[1]}".encode(), hashlib.sha256).hexdigest()
            body = json.dumps({"proof": proof}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path == "/v1/workflows/search-gate" and self.headers.get("Authorization") == "Bearer slow":
                time.sleep(0.2)
            else:
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Unavailable)
    server.test_token = "test"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    async def exercise():
        async with Client(mcp_server.mcp) as mcp:
            monkeypatch.setattr(mcp_server, "client", LocalSystemOneClient(base, auth_token="test", timeout=0.05))
            overloaded = await mcp.call_tool("search_gate", {"task": "x"})
            assert overloaded.is_error and "503" in str(overloaded.model_dump())
            server.test_token = "slow"
            monkeypatch.setattr(mcp_server, "client", LocalSystemOneClient(base, auth_token="slow", timeout=0.05))
            timeout = await mcp.call_tool("search_gate", {"task": "x"})
            assert timeout.is_error and "timed out" in str(timeout.model_dump())

    try:
        asyncio.run(exercise())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
