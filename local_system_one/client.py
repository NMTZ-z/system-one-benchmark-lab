"""Small dependency-free client for Local System One."""

from __future__ import annotations

import json
import ipaddress
import http.client
from pathlib import Path
import urllib.parse
from typing import Any

from .security import read_access_token, verified_request


class LocalSystemOneClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8787",
        *,
        auth_token: str | None = None,
        auth_token_file: str | Path | None = None,
        timeout: float = 5.0,
    ):
        if auth_token and auth_token_file:
            raise ValueError("select one authentication source")
        parts = urllib.parse.urlsplit(base_url)
        try:
            loopback = parts.hostname == "localhost" or ipaddress.ip_address(parts.hostname or "").is_loopback
            _ = parts.port
        except ValueError:
            loopback = False
        if (parts.scheme != "http" or not loopback or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise ValueError("Local System One requires a loopback HTTP origin")
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.auth_token_file = Path(auth_token_file) if auth_token_file else None
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        try:
            credential = read_access_token(self.auth_token_file) if self.auth_token_file else self.auth_token
        except (OSError, ValueError):
            raise RuntimeError("Local System One access token is unavailable") from None
        if not credential:
            raise RuntimeError("Local System One HTTP 401")
        try:
            status, data = verified_request(self.base_url, method, path, body, credential, self.timeout)
            if status >= 400:
                raise RuntimeError(f"Local System One HTTP {status}")
            if len(data) > 1_048_576:
                raise RuntimeError("Local System One response is too large")
            return json.loads(data.decode("utf-8"))
        except (OSError, TimeoutError, http.client.HTTPException):
            raise RuntimeError("Local System One is unreachable or timed out") from None

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

    def notification_gate(
        self,
        event: str,
        *,
        context: Any = None,
        urgency: str = "auto",
        user_action_required: bool = False,
        blocking_failure: bool = False,
        routine_update: bool = False,
        deadline_minutes: int | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "event": event,
            "urgency": urgency,
            "user_action_required": user_action_required,
            "blocking_failure": blocking_failure,
            "routine_update": routine_update,
        }
        if context is not None:
            payload["context"] = context
        if deadline_minutes is not None:
            payload["deadline_minutes"] = deadline_minutes
        if request_id is not None:
            payload["request_id"] = request_id
        return self._request("POST", "/v1/workflows/notification-gate", payload)

    def completion_gate(
        self, task: str, current_result: str, execution_state: dict[str, Any], *, request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {"task": task, "current_result": current_result, "execution_state": execution_state}
        if request_id is not None:
            payload["request_id"] = request_id
        return self._request("POST", "/v1/workflows/completion-gate", payload)

    def retry_escalation_gate(
        self, failure: dict[str, Any], operation: dict[str, Any], history: dict[str, Any],
        constraints: dict[str, Any], *, backend: str = "auto", request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {"failure": failure, "operation": operation, "history": history,
                   "constraints": constraints, "backend": backend}
        if request_id is not None:
            payload["request_id"] = request_id
        return self._request("POST", "/v1/workflows/retry-escalation-gate", payload)

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
