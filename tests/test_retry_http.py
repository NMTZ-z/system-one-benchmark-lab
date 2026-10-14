"""Phase 8C real loopback HTTP contract and failure injection tests (mock backend)."""

from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from local_system_one.service import create_server
from test_retry_escalation_gate import payload


class NeverCalledEngine:
    def decide(self, request):
        raise AssertionError("hard rule must not invoke Laya")


@pytest.fixture
def service():
    server = create_server(NeverCalledEngine(), port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def _post(base, body, *, raw=False):
    data = body if raw else json.dumps(body).encode("utf-8")
    with urlopen(Request(
        f"{base}/v1/workflows/retry-escalation-gate",
        data=data, headers={"content-type":"application/json"},method="POST",
    ), timeout=2) as response:
        return response.status, json.loads(response.read())


def test_live_http_write_timeout_verified_state(service):
    status, body = _post(service,payload())
    assert status == 200
    assert body["guarded_decision"] == "verify_state"
    assert body["raw_model_decision"] is None
    assert body["advisory_only"] is True
    assert body["backend"] == "rule"
    assert body["request_id"] == "phase8c-t1"


def test_live_http_fails_closed_on_bad_context_without_leaking(service):
    bad=payload(unexpected_field="MALFORMED_DATA_SENTINEL")
    with pytest.raises(HTTPError) as err:
        _post(service,bad)
    assert err.value.code == 400
    body=json.loads(err.value.read())
    assert body["error"]=="invalid_request"
    assert "MALFORMED_DATA_SENTINEL" not in str(body)


@pytest.mark.parametrize("shape", [b'not-json',b'{"failure":null}', b'[]',b'{}'])
def test_live_http_invalid_payload_400(service,shape):
    with pytest.raises(HTTPError) as err:
        _post(service,shape,raw=True)
    assert err.value.code==400


@pytest.mark.parametrize("mutation", ["write", "git_push", "pr_create"])
def test_live_http_rejects_known_mutation_masked_as_no_side_effect(service, mutation):
    # Validate safety facts before inference. Laya cannot authorize a lie.
    unsafe = payload(
        operation={
            "type": mutation, "side_effect": "none",
            "side_effect_status": "none", "idempotency": "verified",
            "metadata_source": "adapter_policy",
        },
        failure={"outcome_known": True},
    )
    with pytest.raises(HTTPError) as err:
        _post(service, unsafe)
    assert err.value.code == 400
    response = json.loads(err.value.read())
    assert response["error"] == "invalid_request"


def test_live_http_security_401_with_explicit_auth():
    server=create_server(NeverCalledEngine(),port=0,auth_token="test-secret")
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with pytest.raises(HTTPError) as err:
            _post(f"http://127.0.0.1:{server.server_address[1]}",payload())
        assert err.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
