"""Privacy-safe in-memory service metrics."""

from __future__ import annotations

import statistics
from collections import Counter, deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any


class ServiceMetrics:
    def __init__(self, recent_limit: int = 512):
        self._lock = Lock()
        self._requests = 0
        self._errors = 0
        self._backends: Counter[str] = Counter()
        self._routes: Counter[str] = Counter()
        self._latencies: deque[float] = deque(maxlen=recent_limit)

    def record(
        self,
        *,
        backend: str,
        route_reason: str,
        latency_ms: float,
    ) -> None:
        with self._lock:
            self._requests += 1
            self._backends[backend] += 1
            self._routes[route_reason] += 1
            self._latencies.append(float(latency_ms))

    def record_error(self) -> None:
        with self._lock:
            self._errors += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            values = list(self._latencies)
            return {
                "requests": self._requests,
                "errors": self._errors,
                "backends": dict(self._backends),
                "route_reasons": dict(self._routes),
                "recent_latency_ms": {
                    "samples": len(values),
                    "mean": statistics.fmean(values) if values else None,
                    "p50": statistics.median(values) if values else None,
                    "max": max(values) if values else None,
                },
            }

# Each entry point opens a scope. Nested Engine/Workflow/HTTP layers share it,
# but the marker is reset between requests, even if a runtime re-raises the very
# same exception instance. An immutable set avoids shared mutable task context.
_ERROR_SCOPE: ContextVar[frozenset[ServiceMetrics] | None] = ContextVar(
    "local_system_one_error_scope", default=None
)


@contextmanager
def error_accounting_scope() -> Iterator[None]:
    """Deduplicate errors within one decision/HTTP request, not per exception."""
    if _ERROR_SCOPE.get() is not None:
        yield
        return
    reset_handle = _ERROR_SCOPE.set(frozenset())
    try:
        yield
    finally:
        _ERROR_SCOPE.reset(reset_handle)


def record_error_once(metrics: ServiceMetrics, _error: BaseException) -> bool:
    """Count a failure once in the active request, across nested layers.

    Exception identity is deliberately ignored: a cached exception raised in a
    later request must count again. Entry points establish/reset the scope.
    """
    already_recorded = _ERROR_SCOPE.get()
    if already_recorded is not None and metrics in already_recorded:
        return False
    metrics.record_error()
    if already_recorded is not None:
        _ERROR_SCOPE.set(already_recorded | {metrics})
    return True
