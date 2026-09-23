"""Minimal TypeSafe System One / Jev HTTP adapter."""

from __future__ import annotations

import getpass
import json
import os
import pwd
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _default_keychain_account() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, AttributeError):
        return getpass.getuser()


def _keychain_password(service: str, account: str) -> str | None:
    if sys.platform != "darwin":
        return None
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            account,
            "-s",
            service,
            "-w",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


class JevClient:
    def __init__(
        self,
        *,
        model: str = "jev-1.13.0",
        api_key_env: str = "TYPESAFE_API_KEY",
        keychain_service: str = "typesafe-systemone",
        keychain_account: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        api_key = os.environ.get(api_key_env)
        credential_source = f"env:{api_key_env}"
        if not api_key:
            account = (
                keychain_account
                or os.environ.get("TYPESAFE_KEYCHAIN_ACCOUNT")
                or _default_keychain_account()
            )
            service = os.environ.get("TYPESAFE_KEYCHAIN_SERVICE") or keychain_service
            api_key = _keychain_password(service, account)
            credential_source = f"keychain:{service}/{account}"
        if not api_key:
            raise RuntimeError(
                "missing TypeSafe API key: set TYPESAFE_API_KEY or store it in "
                "macOS Keychain service 'typesafe-systemone'"
            )
        self._api_key = api_key
        self.credential_source = credential_source
        self.model = model
        self.base_url = (
            base_url or os.environ.get("TYPESAFE_BASE_URL") or "https://api.typesafe.ai"
        ).rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        attempts: int = 5,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        retryable_http = {408, 429, 500, 502, 503, 504}

        for attempt in range(1, attempts + 1):
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
                if error.code not in retryable_http or attempt >= attempts:
                    raise RuntimeError(
                        f"TypeSafe HTTP {error.code}: {detail}"
                    ) from error
            except (urllib.error.URLError, TimeoutError, ssl.SSLError) as error:
                if attempt >= attempts:
                    raise RuntimeError(
                        f"TypeSafe request failed after {attempts} attempts: "
                        f"{type(error).__name__}"
                    ) from error

            time.sleep(min(0.75 * (2 ** (attempt - 1)), 6.0))

        raise AssertionError("unreachable retry loop")

    def list_models(self) -> dict[str, Any]:
        return self._request("GET", "/v1/models")

    def predict(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/systemone",
            {"state": state, "questions": questions, "model": self.model},
        )
