"""Pinned TypeSafe Jev HTTP adapter for explicitly authorized, synthetic research.

No production use, no automatic remote fallback, no retries, no configurable URL.
"""
from __future__ import annotations

import json
import os
import pwd
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .contract import (
    ModelCapabilities, ModelContractError, TypedRequest, TypedResult,
    finite_number, probability,
)

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
PRICE_USD_PER_INPUT_TOKEN = 0.042 / 1_000_000  # Docs checked 2026-10-15.
MAX_RESPONSE_BYTES = 65536
KEYCHAIN_SERVICE = "typesafe-systemone"


def _load_api_key() -> str | None:
    """Prefer the environment; reuse the existing macOS Keychain item safely.

    Never pass the secret on the command line or print/capture it in logs.
    Retrieval happens only when the caller opted into a bounded remote request.
    """
    env_key = os.environ.get("TYPESAFE_API_KEY")
    if env_key:
        return env_key
    if sys.platform != "darwin":
        return None
    try:
        user = pwd.getpwuid(os.getuid()).pw_name
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
             "-a", user, "-w"],
            capture_output=True, text=True, check=False, timeout=4,
        )
    except (OSError, subprocess.TimeoutExpired, KeyError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\r\n") or None


class RemoteDisabled(PermissionError):
    """Explicit network/data/budget authorization is absent."""


class BudgetExhausted(RuntimeError):
    """Attempt limit, input bound or estimated budget exhausted."""


class VersionDrift(ModelContractError):
    """Server did not honor the pinned concrete model ID."""


class ProviderHTTPError(RuntimeError):
    """Remote API failure with no secret-bearing response body."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderHTTPError("TypeSafe redirect refused")


def _transport(request: urllib.request.Request, timeout: float, limit: int) -> bytes:
    # System certificate verification remains enabled. Redirects are forbidden.
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.geturl() != ENDPOINT:
                raise ProviderHTTPError("unexpected remote endpoint")
            raw = response.read(limit + 1)
    except urllib.error.HTTPError as exc:
        # No response body, headers, URL with embedded credentials, or raw exception.
        raise ProviderHTTPError(f"TypeSafe HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderHTTPError("TypeSafe transport failure") from None
    if len(raw) > limit:
        raise ModelContractError("remote response exceeds size limit")
    return raw


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelContractError("duplicate JSON response key")
        result[key] = value
    return result


def _decode_response(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
        raise ModelContractError("remote response invalid or too large")
    try:
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ModelContractError("non-finite JSON")),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ModelContractError("invalid remote JSON") from exc
    if not isinstance(payload, dict):
        raise ModelContractError("remote JSON must be an object")
    return payload


def _validated_usage(payload: dict[str, Any]) -> dict[str, int] | None:
    # A response can be billable even if its model ID or answer is invalid.
    # Isolate trustworthy top-level usage from the rest of answer validation.
    usage = payload.get("usage")
    if usage is None:
        return None
    if not isinstance(usage, dict) or set(usage) != {"input_tokens", "output_tokens"}:
        raise ModelContractError("invalid remote token usage")
    if any(type(v) is not int or not 0 <= v <= 2**53 - 1 for v in usage.values()):
        raise ModelContractError("invalid remote token usage")
    return usage


def parse_response(raw: bytes, request: TypedRequest, model: str, elapsed_ms: float) -> TypedResult:
    payload = _decode_response(raw)
    usage = _validated_usage(payload)
    if not isinstance(payload.get("model"), str):
        raise ModelContractError("remote model ID missing")
    resolved = payload["model"]
    if resolved != model:
        raise VersionDrift("returned model differs from pinned model")
    answers = payload.get("answers")
    if not isinstance(answers, dict) or set(answers) != {"decision"}:
        raise ModelContractError("remote question ID set mismatch")
    answer = answers["decision"]
    if not isinstance(answer, dict) or answer.get("type") != request.primitive:
        raise ModelContractError("remote answer type mismatch")
    confidence = answer.get("confidence")
    if confidence is not None:
        confidence = probability(confidence, "confidence")
    if request.primitive == "choice":
        decision = answer.get("choice")
        probs = answer.get("probabilities")
    elif request.primitive == "score":
        decision = answer.get("score")
        probs = answer.get("probabilities")
        legend = answer.get("legend")
        expected = {str(i): item for i, item in enumerate(request.criteria)}
        if legend != expected:
            raise ModelContractError("remote score legend does not match requested levels")
    else:
        p = probability(answer.get("noul"), "noul")
        decision = p >= 0.5
        probs = {"true": p, "false": 1 - p}
    return TypedResult(
        primitive=request.primitive, decision=decision, probabilities=probs,
        provider_id="jev", model_requested=model, model_resolved=resolved,
        execution_backend="remote_http", request_id=request.request_id,
        latency_ms=elapsed_ms, usage=usage, provider_confidence=confidence,
    ).validate_against(request)


class JEVProvider:
    provider_id = "jev"
    capabilities = ModelCapabilities(frozenset({"choice", "score", "noul"}), True, True, True)

    def __init__(
        self, *, model: str = "jev-1.13.0", allow_remote: bool = False,
        public_data_confirmed: bool = False, max_requests: int = 0,
        max_body_bytes: int = 4096, max_total_usd: float = 0.0,
        timeout_seconds: float = 6.0,
        transport: Callable[[urllib.request.Request, float, int], bytes] | None = None,
    ):
        if not re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", model):
            raise ValueError("pin a concrete Jev version; aliases are not reproducible")
        if type(max_requests) is not int or max_requests < 0 or max_requests > 100:
            raise ValueError("max_requests must be an integer in [0,100]")
        if type(max_body_bytes) is not int or not 1 <= max_body_bytes <= 32768:
            raise ValueError("max_body_bytes must be 1-32768")
        if not 0 < finite_number(timeout_seconds, "timeout_seconds") <= 30:
            raise ValueError("timeout must be in (0,30]")
        if not 0 <= finite_number(max_total_usd, "max_total_usd") <= 10:
            raise ValueError("max_total_usd must be [0,10]")
        self.model = model
        self.allow_remote = allow_remote
        self.public_data_confirmed = public_data_confirmed
        self.max_requests = max_requests
        self.max_body_bytes = max_body_bytes
        self.max_total_usd = max_total_usd
        self.timeout_seconds = timeout_seconds
        self._transport = transport or _transport
        self._lock = threading.Lock()
        self._attempts = 0
        self._reserved_estimate_usd = 0.0
        self._measured_usd = 0.0
        self._usage_unknown_attempts = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def measured_usd(self) -> float:
        # Usage-based lower bound; never claim this is the account invoice.
        return self._measured_usd

    @property
    def usage_unknown_attempts(self) -> int:
        return self._usage_unknown_attempts

    def evaluate(self, request: TypedRequest) -> TypedResult:
        if not (self.allow_remote and self.public_data_confirmed):
            raise RemoteDisabled("remote Jev requires consent for public/synthetic input")
        body = json.dumps(
            {"state": request.state, "model": self.model,
             "questions": {"decision": request.to_question()}},
            ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > self.max_body_bytes:
            raise BudgetExhausted("remote input exceeds configured byte bound")
        # This is a pessimistic estimate, NOT a contractual billing ceiling.
        # Actual account invoice is authoritative; stop if observed budget exceeded.
        reserve_usd = (len(body) * 2 + 2048) * PRICE_USD_PER_INPUT_TOKEN
        with self._lock:
            if (self._attempts >= self.max_requests or
                self._reserved_estimate_usd + reserve_usd > self.max_total_usd or
                self._measured_usd > self.max_total_usd):
                raise BudgetExhausted("remote attempt/estimated cost budget exhausted")
            key = _load_api_key()
            if not key:
                raise RemoteDisabled("TypeSafe credential unavailable")
            self._attempts += 1  # Count failures too. Zero automatic retries.
            self._usage_unknown_attempts += 1
            self._reserved_estimate_usd += reserve_usd
        req = urllib.request.Request(
            ENDPOINT, data=body, method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        )
        started = time.perf_counter()
        raw = self._transport(req, self.timeout_seconds, MAX_RESPONSE_BYTES)
        # Count reliable usage even if model/version/answer validation later fails.
        # Unknown usage remains an explicit unknown-billing attempt.
        usage = _validated_usage(_decode_response(raw))
        if usage is not None:
            with self._lock:
                self._measured_usd += usage["input_tokens"] * PRICE_USD_PER_INPUT_TOKEN
                self._usage_unknown_attempts -= 1
        return parse_response(raw, request, self.model, (time.perf_counter() - started) * 1000)
