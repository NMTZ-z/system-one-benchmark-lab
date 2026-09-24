"""Small dependency-free client for Local System One."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class LocalSystemOneClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8787",
        *,
        auth_token: str | None = None,
        timeout: float = 5.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(
                f"Local System One HTTP {error.code}: {detail}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError("Local System One is unreachable") from error

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def metrics(self) -> dict[str, Any]:
        return self._request("GET", "/metrics")

    def model_tier_gate(
        self,
        task: str,
        *,
        context: Any = None,
        risk: str = "auto",
        task_type: str = "auto",
        irreversible: bool = False,
        requires_precision: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "task": task,
            "risk": risk,
            "task_type": task_type,
            "irreversible": irreversible,
            "requires_precision": requires_precision,
        }
        if context is not None:
            payload["context"] = context
        if request_id is not None:
            payload["request_id"] = request_id
        return self._request("POST", "/v1/workflows/model-tier-gate", payload)

    def search_gate(
        self,
        task: str,
        *,
        context: Any = None,
        freshness: str = "auto",
        source_scope: str = "auto",
        external_lookup_required: bool = False,
        provided_context_sufficient: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "task": task,
            "freshness": freshness,
            "source_scope": source_scope,
            "external_lookup_required": external_lookup_required,
            "provided_context_sufficient": provided_context_sufficient,
        }
        if context is not None:
            payload["context"] = context
        if request_id is not None:
            payload["request_id"] = request_id
        return self._request("POST", "/v1/workflows/search-gate", payload)
