"""Privacy-safe in-memory service metrics."""

from __future__ import annotations

import statistics
from collections import Counter, deque
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

_ERROR_RECORDED_ATTR = "_local_system_one_metrics_error_recorded"


def record_error_once(metrics: ServiceMetrics, error: BaseException) -> bool:
    """Record one service error even when an exception crosses multiple layers.

    Decision/runtime failures can pass through the engine, a workflow fail-open
    boundary, and the HTTP service. Mark the exception object after the first
    count so outer layers do not count the same failure again.
    """
    if bool(getattr(error, _ERROR_RECORDED_ATTR, False)):
        return False
    metrics.record_error()
    try:
        setattr(error, _ERROR_RECORDED_ATTR, True)
    except Exception:  # noqa: BLE001,S110 - never mask the original error
        pass
    return True
