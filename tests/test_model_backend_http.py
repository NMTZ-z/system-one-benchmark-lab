"""Failure-only HTTP transport tests: no outbound traffic or credentials."""
from __future__ import annotations

import urllib.error
import urllib.request

import pytest

from local_system_one.model_backends.contract import ModelContractError
from local_system_one.model_backends.jev import (
    ENDPOINT, ProviderHTTPError, _NoRedirect, _transport,
)


@pytest.mark.parametrize("status", [401, 403, 408, 429, 500, 529])
def test_http_errors_do_not_log_response_or_authorization(monkeypatch, status):
    class Opener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, status, "PRIVATE_BODY_SHOULD_NOT_LEAK", {}, None,
            )
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    req = urllib.request.Request(
        ENDPOINT, data=b"{}", method="POST",
        headers={"Authorization": "Bearer fake-top-secret-value"},
    )
    with pytest.raises(ProviderHTTPError, match=f"HTTP {status}") as caught:
        _transport(req, 1, 10)
    assert "PRIVATE_BODY_SHOULD_NOT_LEAK" not in str(caught.value)
    assert "fake-top-secret-value" not in str(caught.value)


def test_redirect_and_oversized_response_refused(monkeypatch):
    with pytest.raises(ProviderHTTPError, match="redirect"):
        _NoRedirect().redirect_request(None, None, 302, "moved", {}, "https://example.org")
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def geturl(self):
            return ENDPOINT
        def read(self, limit):
            return b"X" * (limit + 1)
    class Opener:
        def open(self, request, timeout):
            return Response()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(ModelContractError, match="size limit"):
        _transport(urllib.request.Request(ENDPOINT), 1, 10)
