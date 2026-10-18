"""Provider budget unit tests. Upstream is LOCAL fake HTTP, never a real model."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread, Lock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_provider_cap import BudgetLedger, make_server


@contextmanager
def _running(server):
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@contextmanager
def _provider():
    seen = []
    lock = Lock()

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_POST(self):  # noqa: N802
            size = int(self.headers["Content-Length"])
            body = self.rfile.read(size)
            with lock:
                seen.append(body)
            if self.path != "/step_plan/v1/chat/completions":
                self.send_error(404)
                return
            if b'"trigger_503"' in body:
                response = b'{"error":"fake_upstream_failure"}'
                self.send_response(503)
                content_type = "application/json"
            else:
                response = b'data: {"choices":[]}\n\ndata: [DONE]\n\n'
                self.send_response(200)
                content_type = "text/event-stream"
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    with _running(server) as url:
        yield url + "/step_plan/v1/chat/completions", seen


def _call(url, *, model="step-5-preview", secret="NEVER_SAVE_SECRET", body=None):
    payload = body if body is not None else json.dumps({
        "model": model, "messages": [{"role": "user", "content": secret}],
    }).encode()
    req = Request(url + "/chat/completions", data=payload, method="POST",
                  headers={"Authorization": "Bearer PRIVATE_PROVIDER_KEY_VALUE_123",
                           "Content-Type": "application/json", "Accept": "text/event-stream"})
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def test_real_forwarding_shape_and_hard_per_run_cap(tmp_path):
    with _provider() as (upstream, seen):
        ledger = BudgetLedger(tmp_path / "ledger.jsonl", total_limit=9, per_run_limit=2)
        server = make_server(port=0, ledger=ledger, run="hermes_success", upstream=upstream)
        with _running(server) as proxy:
            a = _call(proxy)
            b = _call(proxy)
            c = _call(proxy)
        assert a == b == (200, b'data: {"choices":[]}\n\ndata: [DONE]\n\n')
        assert c[0] == 429
        assert len(seen) == 2 and all(b"NEVER_SAVE_SECRET" in item for item in seen)
        report = ledger.path.read_text()
        assert "NEVER_SAVE_SECRET" not in report
        assert "PRIVATE_PROVIDER_KEY_VALUE" not in report
        assert ledger.counts("hermes_success") == (2, 2)
        assert sum(json.loads(l)["kind"] == "result" for l in report.splitlines()) == 2


def test_global_cap_shared_by_two_separate_run_proxies(tmp_path):
    with _provider() as (upstream, seen):
        ledger = BudgetLedger(tmp_path / "ledger.jsonl", total_limit=3, per_run_limit=2)
        with _running(make_server(port=0, ledger=ledger, run="off", upstream=upstream)) as a:
            assert _call(a)[0] == _call(a)[0] == 200
            assert _call(a)[0] == 429
        with _running(make_server(port=0, ledger=ledger, run="shadow", upstream=upstream)) as b:
            assert _call(b)[0] == 200
            assert _call(b)[0] == 429
        assert len(seen) == 3
        assert ledger.counts("off") == (3, 2)
        assert ledger.counts("shadow") == (3, 1)


def test_concurrent_requests_cannot_overspend_limit(tmp_path):
    with _provider() as (upstream, seen):
        ledger = BudgetLedger(tmp_path / "ledger.jsonl", total_limit=3, per_run_limit=3)
        with _running(make_server(port=0, ledger=ledger, run="race", upstream=upstream)) as url:
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(lambda _: _call(url)[0], range(12)))
        assert statuses.count(200) == 3
        assert statuses.count(429) == 9
        assert len(seen) == 3
        assert ledger.counts("race") == (3, 3)


def test_bad_key_or_model_does_not_consume_slot(tmp_path):
    with _provider() as (upstream, seen):
        ledger = BudgetLedger(tmp_path / "ledger.jsonl", total_limit=2, per_run_limit=2)
        with _running(make_server(port=0, ledger=ledger, run="bad", upstream=upstream)) as url:
            assert _call(url, model="other-provider-unknown")[0] == 400
            assert _call(url, body=b'not-json')[0] == 400
            with pytest.raises(HTTPError) as bad:
                urlopen(Request(url + "/chat/completions", data=b'{}', method="POST"), timeout=2)
            assert bad.value.code == 401
        assert seen == []
        assert ledger.counts("bad") == (0, 0)


def test_provider_http_503_still_consumes_a_slot(tmp_path):
    with _provider() as (upstream, seen):
        ledger = BudgetLedger(tmp_path / "ledger.jsonl", total_limit=1, per_run_limit=1)
        with _running(make_server(port=0, ledger=ledger, run="server_failure", upstream=upstream)) as url:
            assert _call(url, secret="trigger_503")[0] == 503
            assert _call(url)[0] == 429
        assert len(seen) == 1
        statuses = [json.loads(l).get("http_status") for l in ledger.path.read_text().splitlines()]
        assert 503 in statuses
        assert ledger.counts("server_failure") == (1, 1)


def test_corrupted_budget_fails_closed_not_resets(tmp_path):
    file = tmp_path / "ledger.jsonl"
    file.write_text('{"kind":"reserved","run":"old","slot":1}\nINVALID-TRAIL\n')
    with _provider() as (upstream, seen):
        ledger = BudgetLedger(file, total_limit=20, per_run_limit=10)
        with _running(make_server(port=0, ledger=ledger, run="new", upstream=upstream)) as url:
            assert _call(url)[0] == 503
        assert seen == []
        with pytest.raises(ValueError):
            ledger.counts("new")
