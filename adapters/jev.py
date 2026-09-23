"""Minimal TypeSafe System One / Jev HTTP adapter."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class JevClient:
    def __init__(
        self,
        *,
        model: str = "jev-1.13.0",
        api_key_env: str = "TYPESAFE_API_KEY",
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key environment variable: {api_key_env}")
        self._api_key = api_key
        self.model = model
        self.base_url = (
            base_url or os.environ.get("TYPESAFE_BASE_URL") or "https://api.typesafe.ai"
        ).rstrip("/")
        self.timeout = timeout

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "system-one-benchmark-lab/phase3",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"TypeSafe HTTP {error.code}: {detail}") from error

    def list_models(self) -> dict[str, Any]:
        return self._request("GET", "/v1/models")

    def predict(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/systemone",
            {"state": state, "questions": questions, "model": self.model},
        )
