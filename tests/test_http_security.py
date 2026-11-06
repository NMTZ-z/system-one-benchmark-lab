from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from local_system_one import first_run, service
from local_system_one.metrics import ServiceMetrics
from local_system_one.security import read_access_token
from local_system_one.client import LocalSystemOneClient


class Engine:
    def __init__(self):
        self.metrics = ServiceMetrics()
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def decide(self, _request):
        self.calls += 1
        self.started.set()
        assert self.release.wait(3)
        return {"decision": "ok"}


@pytest.fixture
def runtime():
    engine = Engine()
    server = service.create_server(engine, port=0, auth_token="test-secret")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield engine, server.server_address[1]
    finally:
        engine.release.set()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def request(port, body, token="test-secret"):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"http://127.0.0.1:{port}/v1/choice", data=json.dumps(body).encode(), headers=headers)
    try:
        with urlopen(req, timeout=2) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_auth_loopback_and_request_size(runtime):
    engine, port = runtime
    body = {"state": {}, "instructions": "choose", "criteria": ["a", "b"]}
    assert request(port, body, None)[0] == 401
    assert request(port, body, "wrong")[0] == 401
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    connection.putrequest("POST", "/v1/choice")
    connection.putheader("Authorization", "Bearer test-secret")
    connection.putheader("Content-Length", str(service.MAX_BODY_BYTES + 1))
    connection.endheaders()
    assert connection.getresponse().status == 413
    connection.close()
    assert engine.calls == 0
    engine.release.set()
    assert request(port, body) == (200, {"decision": "ok"})
    with pytest.raises(ValueError):
        service.create_server(engine, host="0.0.0.0", port=0, auth_token="test-secret")
    with pytest.raises(ValueError):
        service.create_server(engine, port=0)


def test_stalled_inference_times_out_and_does_not_queue(runtime, monkeypatch):
    engine, port = runtime
    monkeypatch.setattr(service, "REQUEST_TIMEOUT_SECONDS", 0.2)
    body = {"state": {}, "instructions": "choose", "criteria": ["a", "b"]}
    result = []
    caller = threading.Thread(target=lambda: result.append(request(port, body)))
    caller.start()
    assert engine.started.wait(1)
    assert request(port, body) == (503, {"error": "overloaded"})
    caller.join(timeout=2)
    assert result == [(504, {"error": "request_timeout"})]
    assert request(port, body)[0] == 503
    assert engine.calls == 1
    engine.release.set()


def test_private_token_file_rejects_links_and_unsafe_permissions(tmp_path):
    token, created = first_run._access_token(tmp_path)
    assert created and read_access_token(tmp_path / "access-token") == token
    (tmp_path / "access-token").chmod(0o644)
    with pytest.raises(ValueError):
        read_access_token(tmp_path / "access-token")
    (tmp_path / "access-token").chmod(0o600)
    (tmp_path / "alias").symlink_to(tmp_path / "access-token")
    with pytest.raises(OSError):
        read_access_token(tmp_path / "alias")


def test_impostor_listener_receives_neither_token_nor_task():
    received = []

    class Impostor(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            received.append((self.path, self.headers.get("Authorization")))
            body = b'{"proof":"' + b"0" * 64 + b'"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            received.append((self.path, self.headers.get("Authorization")))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Impostor)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = LocalSystemOneClient(f"http://127.0.0.1:{server.server_address[1]}", auth_token="test-secret")
        with pytest.raises(RuntimeError, match="401"):
            client.search_gate("private task sentinel")
        assert received == [("/_local_system_one/identity", None)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_identity_proof_from_another_port_cannot_be_replayed(runtime):
    _, real_port = runtime
    received = []

    class Relay(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            request = Request(f"http://127.0.0.1:{real_port}/_local_system_one/identity",
                              headers={"X-Local-System-One-Challenge": self.headers["X-Local-System-One-Challenge"]})
            with urlopen(request, timeout=2) as response:
                proof = response.read()
            self.send_response(200)
            self.send_header("Content-Length", str(len(proof)))
            self.end_headers()
            self.wfile.write(proof)

        def do_POST(self):
            received.append(self.headers.get("Authorization"))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Relay)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = LocalSystemOneClient(f"http://127.0.0.1:{server.server_address[1]}", auth_token="test-secret")
        with pytest.raises(RuntimeError, match="401"):
            client.search_gate("private task sentinel")
        assert received == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
