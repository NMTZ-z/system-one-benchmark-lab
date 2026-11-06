"""Process-local, fail-closed no-retry guard for the frozen Hermes H4E one-shot."""
from __future__ import annotations

import functools
import importlib
import math
from pathlib import Path
import threading
import time

MODULE_REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_SOURCE = MODULE_REPO_ROOT / "private" / "phase8_3_h4e_real" / "source"
MODEL = "step-5-preview"
PROVIDER = "stepfun"
BASE_URL = "http://127.0.0.1:18794"
RUN_TOKEN_HEADER = "X-H4E-Run-Token"
REQUEST_SEQUENCE_HEADER = "X-H4E-Logical-Request"
_STOP_MESSAGE = "H4E stopped by the no-retry request guard"
_MAX_SECONDS = 90.0
_MAX_REQUESTS = 3


class H4EStop(BaseException):
    """Fixed, sanitized stop signal that bypasses Hermes ``except Exception`` retries."""

    def __init__(self) -> None:
        super().__init__(_STOP_MESSAGE)


class _Epoch:
    __slots__ = ("index", "create_calls")

    def __init__(self, index: int) -> None:
        self.index = index
        self.create_calls = 0


class _Guard:
    def __init__(self, deadline: float, run_token: str) -> None:
        self._deadline = deadline
        self._run_token = run_token
        self._lock = threading.RLock()
        self._active_epoch: _Epoch | None = None
        self._sequence = 0
        self._stopped = False
        self._stats = {
            "logical_epochs": 0,
            "sdk_create_attempts": 0,
            "blocked_requests": 0,
            "route_rejections": 0,
            "resolver_failures": 0,
            "client_failures": 0,
            "worker_stops_forwarded": 0,
            "stream_errors_sanitized": 0,
            "deadline_stops": 0,
            "explicit_key_rejections": 0,
            "stopped": 0,
        }

    def report(self) -> dict[str, int]:
        """Return counters only; never expose the run token, payload or exception text."""
        with self._lock:
            return dict(self._stats)

    def _deny(self, counter: str = "blocked_requests") -> None:
        with self._lock:
            self._stats[counter] += 1
            self._stopped = True
            self._stats["stopped"] = 1
        raise H4EStop() from None

    def _latch(self) -> None:
        with self._lock:
            self._stopped = True
            self._stats["stopped"] = 1

    def _ensure_active(self) -> None:
        with self._lock:
            if self._stopped:
                self._stats["blocked_requests"] += 1
                raise H4EStop() from None

    def _check_deadline(self) -> float:
        self._ensure_active()
        remaining = self._deadline - time.monotonic()
        if not math.isfinite(remaining) or remaining <= 0.0:
            self._deny("deadline_stops")
        return remaining

    def _check_route(self, provider: object, model: object, base_url: object, api_mode: object | None = None) -> None:
        if (not isinstance(provider, str) or provider.strip().lower() != PROVIDER
                or model != MODEL or not _is_fixed_base_url(base_url)
                or (api_mode is not None and api_mode != "chat_completions")):
            self._deny("route_rejections")

    def _open_epoch(self, agent: object) -> _Epoch:
        self._check_deadline()
        self._check_route(
            getattr(agent, "provider", None), getattr(agent, "model", None),
            getattr(agent, "base_url", None), getattr(agent, "api_mode", None),
        )
        if (getattr(agent, "_api_max_retries", None) != 1
                or getattr(agent, "_auto_recovery_cycles", None) != 0
                or getattr(agent, "_fallback_chain", ())):
            self._deny()
        with self._lock:
            if self._active_epoch is not None:
                self._deny()
            self._stats["logical_epochs"] += 1
            epoch = _Epoch(self._stats["logical_epochs"])
            self._active_epoch = epoch
            return epoch

    def _close_epoch(self, epoch: _Epoch) -> None:
        with self._lock:
            if self._active_epoch is epoch:
                self._active_epoch = None

    def _guarded_create(self, original, resource, *args, **kwargs):
        self._check_deadline()
        try:
            client = getattr(resource, "_client")
            self._check_route(PROVIDER, kwargs.get("model"), getattr(client, "base_url", None), "chat_completions")
            if (not type(resource).__module__.startswith("openai.resources.chat.completions")
                    or not type(client).__module__.startswith("openai")
                    or getattr(client, "max_retries", None) != 0):
                self._deny()
            if _has_reserved_header(getattr(client, "default_headers", {})):
                self._deny()
            extra_headers = kwargs.get("extra_headers")
            if _has_reserved_header(extra_headers or {}):
                self._deny()
            headers = dict(extra_headers or {})
        except H4EStop:
            self._latch()
            raise
        except Exception:
            self._deny()

        with self._lock:
            epoch = self._active_epoch
            if epoch is None or epoch.create_calls != 0 or self._sequence >= _MAX_REQUESTS:
                self._deny()
            epoch.create_calls += 1
            self._sequence += 1
            sequence = self._sequence
            self._stats["sdk_create_attempts"] += 1

        headers[RUN_TOKEN_HEADER] = self._run_token
        headers[REQUEST_SEQUENCE_HEADER] = str(sequence)
        kwargs = dict(kwargs)
        kwargs["extra_headers"] = headers
        try:
            return original(resource, *args, **kwargs)
        except H4EStop:
            self._latch()
            raise
        except Exception:
            self._deny()

    def _guarded_stream_iter(self, original, stream):
        try:
            for chunk in original(stream):
                self._check_deadline()
                yield chunk
            self._check_deadline()
        except H4EStop:
            self._latch()
            raise
        except Exception:
            with self._lock:
                self._stats["stream_errors_sanitized"] += 1
            self._latch()
            raise H4EStop() from None


def _is_fixed_base_url(value: object) -> bool:
    return str(value) in (BASE_URL, BASE_URL + "/")


def _has_reserved_header(headers: object) -> bool:
    if headers is None:
        return False
    try:
        items = headers.items()
        for key, _value in items:
            if not isinstance(key, str):
                return True
            if key.casefold() in {RUN_TOKEN_HEADER.casefold(), REQUEST_SEQUENCE_HEADER.casefold()}:
                return True
        return False
    except Exception:
        return True


def _require_runtime_symbols(runtime_provider, oneshot, run_agent, agent_init, runtime_helpers,
                             conversation_loop, stream_helpers, nonstream_helpers,
                             completions_type, stream_type) -> None:
    """Fail closed if imported modules do not expose the pinned runtime call sites."""
    symbols = (
        (runtime_provider, "resolve_runtime_with_fallback"),
        (runtime_provider, "resolve_runtime_provider"),
        (oneshot, "run_oneshot"),
        (oneshot, "_run_agent"),
        (run_agent.AIAgent, "__init__"),
        (agent_init, "_apply_agent_section"),
        (runtime_helpers, "create_openai_client"),
        (conversation_loop, "_run_api_retry_loop"),
        (stream_helpers, "_dispatch_nonstreaming_api_request"),
        (stream_helpers._StreamingCall, "_open_chat_stream"),
        (stream_helpers._StreamingCall, "_handle_stream_error"),
        (stream_helpers._StreamingCall, "_maybe_disable_streaming"),
        (stream_helpers._StreamingCall, "_unmask_server_error_with_nonstreaming"),
        (stream_helpers._StreamingCall, "_call"),
        (stream_helpers._StreamingCall, "_run_call"),
        (nonstream_helpers._NonStreamRequest, "_call"),
        (completions_type, "create"),
        (stream_type, "__iter__"),
    )
    if any(not callable(getattr(owner, name, None)) for owner, name in symbols):
        raise H4EStop() from None
    if (not completions_type.__module__.startswith("openai.resources.chat.completions")
            or stream_type.__module__ not in {"openai", "openai._streaming"}):
        raise H4EStop() from None


def _module(name: str, relative: str):
    module = importlib.import_module(name)
    expected = (FROZEN_SOURCE / relative).resolve(strict=True)
    actual = Path(getattr(module, "__file__", "")).resolve(strict=True)
    if actual != expected:
        raise H4EStop() from None
    return module


_ACTIVE_GUARD: _Guard | None = None


def install_runtime_guards(deadline: float, *, run_token: str) -> _Guard:
    """Install fail-closed guards for one parent-deadline H4E process.

    ``deadline`` is the caller's absolute monotonic deadline; this function never creates a
    replacement budget. ``run_token`` is a parent-generated 64-character hex correlation token.
    """
    global _ACTIVE_GUARD
    if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
            or not math.isfinite(float(deadline)) or not isinstance(run_token, str)
            or len(run_token) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in run_token)):
        raise H4EStop() from None
    remaining = float(deadline) - time.monotonic()
    if not math.isfinite(remaining) or remaining <= 0.0 or remaining > _MAX_SECONDS:
        raise H4EStop() from None
    if _ACTIVE_GUARD is not None:
        raise H4EStop() from None
    guard = _Guard(float(deadline), run_token.lower())
    try:
        runtime_provider = _module("hermes_cli.runtime_provider", "hermes_cli/runtime_provider.py")
        hermes_oneshot = _module("hermes_cli.oneshot", "hermes_cli/oneshot.py")
        run_agent = _module("run_agent", "run_agent.py")
        agent_init = _module("agent.agent_init", "agent/agent_init.py")
        runtime_helpers = _module("agent.agent_runtime_helpers", "agent/agent_runtime_helpers.py")
        conversation_loop = _module("agent.conversation_loop", "agent/conversation_loop.py")
        stream_helpers = _module("agent.chat_completion_helpers", "agent/chat_completion_helpers.py")
        nonstream_helpers = _module("agent.chat_completion_nonstream", "agent/chat_completion_nonstream.py")
        if importlib.import_module('openai').__version__ != '2.24.0':
            raise H4EStop()
        sdk_completions = importlib.import_module("openai.resources.chat.completions")
        sdk_streaming = importlib.import_module("openai._streaming")
        completions_type = getattr(sdk_completions, "Completions")
        stream_type = getattr(sdk_streaming, "Stream")
        _require_runtime_symbols(runtime_provider, hermes_oneshot, run_agent, agent_init, runtime_helpers,
                                 conversation_loop, stream_helpers, nonstream_helpers,
                                 completions_type, stream_type)

        original_resolve = runtime_provider.resolve_runtime_provider
        def no_fallback(_config=None, *, requested=None, target_model=None,
                        explicit_base_url=None, explicit_api_key=None):
            guard._check_deadline()
            if explicit_api_key not in (None, ""):
                guard._deny("explicit_key_rejections")
            if (not isinstance(requested, str) or requested.strip().lower() != PROVIDER
                    or target_model != MODEL or (explicit_base_url and not _is_fixed_base_url(explicit_base_url))):
                guard._deny("route_rejections")
            try:
                resolved = original_resolve(requested=requested, target_model=target_model,
                                            explicit_base_url=explicit_base_url, explicit_api_key=explicit_api_key)
            except H4EStop:
                guard._latch()
                raise
            except Exception:
                guard._deny("resolver_failures")
            if not isinstance(resolved, dict) or resolved.get("provider") != PROVIDER or not _is_fixed_base_url(resolved.get("base_url")):
                guard._deny("route_rejections")
            return resolved, None

        original_init = run_agent.AIAgent.__init__
        def guarded_init(agent, *args, **kwargs):
            guard._check_deadline()
            if args:
                guard._deny()
            guard._check_route(kwargs.get("provider"), kwargs.get("model"), kwargs.get("base_url"))
            kwargs = dict(kwargs)
            kwargs.update(base_url=BASE_URL, provider=PROVIDER, model=MODEL, api_mode="chat_completions",
                          fallback_model=None, run_budget_seconds=guard._check_deadline())
            try:
                original_init(agent, **kwargs)
            except H4EStop:
                guard._latch()
                raise
            except Exception:
                guard._deny("client_failures")
            if (getattr(agent, "_api_max_retries", None) != 1
                    or getattr(agent, "_auto_recovery_cycles", None) != 0
                    or getattr(agent, "run_budget_seconds", None) is None
                    or getattr(agent, "run_budget_seconds", math.inf) > remaining
                    or getattr(agent, "_fallback_chain", ())):
                guard._deny()

        original_apply = agent_init._apply_agent_section
        def guarded_apply(agent, config):
            guard._check_deadline()
            local_config = dict(config or {})
            agent_config = dict(local_config.get("agent") or {})
            agent_config.update(api_max_retries=1, auto_recovery_cycles=0)
            local_config["agent"] = agent_config
            try:
                original_apply(agent, local_config)
            except H4EStop:
                guard._latch()
                raise
            except Exception:
                guard._deny("client_failures")
            agent._api_max_retries = 1
            agent._auto_recovery_cycles = 0

        original_factory = runtime_helpers.create_openai_client
        def guarded_factory(agent, client_kwargs, *, reason, shared):
            guard._check_deadline()
            guard._check_route(getattr(agent, "provider", None), getattr(agent, "model", None),
                               client_kwargs.get("base_url"), getattr(agent, "api_mode", None))
            safe_kwargs = dict(client_kwargs)
            safe_kwargs["max_retries"] = 0
            try:
                client = original_factory(agent, safe_kwargs, reason=reason, shared=shared)
            except H4EStop:
                guard._latch()
                raise
            except Exception:
                guard._deny("client_failures")
            if (not type(client).__module__.startswith("openai") or getattr(client, "max_retries", None) != 0
                    or not _is_fixed_base_url(getattr(client, "base_url", None))):
                guard._deny("client_failures")
            return client

        original_loop = conversation_loop._run_api_retry_loop
        def guarded_loop(agent, state):
            epoch = guard._open_epoch(agent)
            try:
                return original_loop(agent, state)
            except H4EStop:
                guard._latch()
                raise
            finally:
                guard._close_epoch(epoch)

        streaming_class = stream_helpers._StreamingCall
        original_stream_worker = streaming_class._run_call
        def guarded_stream_worker(worker):
            try:
                guard._check_deadline()
                return original_stream_worker(worker)
            except H4EStop:
                guard._latch()
                worker.result["error"] = H4EStop()
                with guard._lock:
                    guard._stats["worker_stops_forwarded"] += 1
                return None

        nonstream_class = nonstream_helpers._NonStreamRequest
        original_nonstream_worker = nonstream_class._call
        def guarded_nonstream_worker(worker):
            try:
                guard._check_deadline()
                return original_nonstream_worker(worker)
            except H4EStop:
                guard._latch()
                worker.result["error"] = H4EStop()
                with guard._lock:
                    guard._stats["worker_stops_forwarded"] += 1
                return None

        original_create = completions_type.create
        @functools.wraps(original_create)
        def guarded_create(resource, *args, **kwargs):
            return guard._guarded_create(original_create, resource, *args, **kwargs)

        original_iter = stream_type.__iter__
        @functools.wraps(original_iter)
        def guarded_iter(stream):
            yield from guard._guarded_stream_iter(original_iter, stream)

        runtime_provider.resolve_runtime_with_fallback = no_fallback
        run_agent.AIAgent.__init__ = guarded_init
        agent_init._apply_agent_section = guarded_apply
        runtime_helpers.create_openai_client = guarded_factory
        conversation_loop._run_api_retry_loop = guarded_loop
        streaming_class._run_call = guarded_stream_worker
        nonstream_class._call = guarded_nonstream_worker
        completions_type.create = guarded_create
        stream_type.__iter__ = guarded_iter
    except H4EStop:
        raise
    except Exception:
        raise H4EStop() from None
    _ACTIVE_GUARD = guard
    return guard
