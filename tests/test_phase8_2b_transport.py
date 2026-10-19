"""8.2B controlled localhost transport tests; no paid Provider or Agent."""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
import urllib.error
import urllib.request

from local_system_one.budget_observability import reconcile_budget
from local_system_one.evidence_integrity import opaque_ref

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from phase8_2a_provider_cap import BudgetLedger, make_server
from phase8_2a_shadow_proxy import Handler as ShadowHandler


@contextmanager
def running(server):
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def post_proxy(url: str, body: dict) -> int:
    req = urllib.request.Request(
        url + "/chat/completions", method="POST",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer SYNTHETIC", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as err:
        err.read()
        return err.code


def events(ledger: BudgetLedger) -> list[dict]:
    return [json.loads(x) for x in ledger.path.read_text().splitlines() if x]


def test_controlled_outlet_records_actual_upstream_response(tmp_path):
    class LocalFake(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def do_POST(self):
            payload = self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(503 if b"trigger_fail" in payload else 200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

    with running(ThreadingHTTPServer(("127.0.0.1", 0), LocalFake)) as upstream:
        ledger = BudgetLedger(tmp_path / "transport.jsonl", total_limit=2, per_run_limit=2)
        with running(make_server(
            port=0, ledger=ledger, run="local", upstream=upstream + "/step_plan/v1/chat/completions"
        )) as proxy:
            assert post_proxy(proxy, {"model": "step-5-preview"}) == 200
            assert post_proxy(proxy, {"model": "step-5-preview", "trigger_fail": True}) == 503
            assert post_proxy(proxy, {"model": "step-5-preview"}) == 429
    record = events(ledger)
    assert [item["kind"] for item in record] == [
        "reserved", "attempted", "responded", "result",
        "reserved", "attempted", "responded", "result",
    ]
    report = reconcile_budget(record, run_id="local", per_run_cap=2, total_cap=2,
                              agent_reported_calls=1, controlled_egress_verified=True)
    assert report["provider_responded"] == report["proxy_attempts"] == 2
    assert report["unattributed_requests"] == 1
    assert report["unknown_cost_requests"] == 2


def test_unreachable_upstream_must_not_be_reported_as_provider_failure_or_response(tmp_path):
    ledger = BudgetLedger(tmp_path / "transport.jsonl", total_limit=1, per_run_limit=1)
    with running(make_server(
        port=0, ledger=ledger, run="offline",
        upstream="http://127.0.0.1:1/step_plan/v1/chat/completions",
    )) as proxy:
        assert post_proxy(proxy, {"model": "step-5-preview"}) == 502
        assert post_proxy(proxy, {"model": "step-5-preview"}) == 429
    record = events(ledger)
    assert [x["kind"] for x in record] == ["reserved", "attempted", "outcome_unknown", "result"]
    report = reconcile_budget(record, run_id="offline", per_run_cap=1, total_cap=1,
                              agent_reported_calls=1, controlled_egress_verified=True)
    assert report["budget_integrity"] == "PARTIAL"
    assert report["provider_responded"] == 0
    assert report["outcome_unknown"] == 1
    assert record[-1]["http_status"] == 502  # Proxy-local status only.


def test_shadow_observer_shared_private_key_correlates_request_id_only(tmp_path):
    class FakeRuntime(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            result = json.dumps({"request_id": req.get("request_id"), "decision": "verify"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

    with running(ThreadingHTTPServer(("127.0.0.1", 0), FakeRuntime)) as runtime:
        ShadowHandler.destination = runtime
        ShadowHandler.evidence_path = tmp_path / "observer.jsonl"
        server = ThreadingHTTPServer(("127.0.0.1", 0), ShadowHandler)
        server.run_id = "contracttest"
        server.run_salt = "private_test_salt"
        key_material = b"x" * 32
        server.correlation_secret = key_material
        with running(server) as observer:
            request = urllib.request.Request(
                observer + "/v1/workflows/completion-gate",
                method="POST",
                data=b'{"request_id":"opaque_private_value","task":"do-not-export"}',
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                assert response.status == 200
        original = ShadowHandler.evidence_path.read_text()
    assert "opaque_private_value" not in original
    assert "do-not-export" not in original
    row = json.loads(original)
    assert row["decision_request_ref"] == opaque_ref(key_material, "decision_request", "opaque_private_value")
    assert row["response_matches_request_id"] is True
    assert row["correlation_status"] == "request_ref_only"
