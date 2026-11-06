"""True localhost HTTP 503 for absent Laya, without any Provider/Agent call."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import json
import os
import socket
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from phase8_2a_shadow_proxy import Handler
from phase8_2b_native_correlate import ref

KEY=b"\x67"*32


@contextmanager
def offline_observer(tmp_path):
    # Do not bind any port used by actual Hermes or physical StepFun proxy.
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    path=tmp_path/"observer.jsonl"
    server.run_salt=os.urandom(16).hex()
    server.correlation_secret=KEY
    server.run_id="h3_synthetic_http_only"
    Handler.destination="http://127.0.0.1:18782"
    Handler.evidence_path=path
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:yield server,path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unavailable_runtime_is_actual_503_and_not_a_model_decision(tmp_path):
    # H3 always preflights 18782 unbound for a deliberately down runtime.
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1",18782))==0:
            import pytest
            pytest.skip("unrelated runtime already listening on H3 test port")
    with offline_observer(tmp_path) as (server,path):
        reqid="isolated_error_probe"
        body=json.dumps({
            "request_id":reqid,
            "task":"synthetic offline file status report",
            "current_result":"file exists but no independent confirmation",
            "execution_state":{"tools_used":1,"tool_failures":0},
        }).encode()
        req=Request(f"http://127.0.0.1:{server.server_port}/v1/workflows/completion-gate",
                    data=body,headers={"Content-Type":"application/json"},
                    method="POST")
        try:
            urlopen(req,timeout=5)
            raise AssertionError("runtime down must fail-open via observer HTTP503")
        except HTTPError as e:
            assert e.code==503
            assert json.loads(e.read())=={"error":"isolated_runtime_unavailable"}
    records=[json.loads(x) for x in path.read_text().splitlines()]
    assert len(records)==1
    row=records[0]
    assert row["http_status"]==503
    assert row["decision_request_ref"]==ref(KEY,"decision_request",reqid)
    assert row["backend"] is None and row["decision_source"] is None
    assert row["response_matches_request_id"] is None
    assert row["run_id"]=="h3_synthetic_http_only"
    assert "task" not in row and "current_result" not in row
