"""Health state for the optional ANE backend."""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass
from typing import Literal

HealthState = Literal["unavailable", "unknown", "healthy", "degraded"]


@dataclass(frozen=True)
class HealthSnapshot:
    state: HealthState
    reason: str
    rolling_p50_ms: float | None
    samples: int
    max_p50_ms: float

    @property
    def healthy(self) -> bool:
        return self.state == "healthy"

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "reason": self.reason,
            "healthy": self.healthy,
            "rolling_p50_ms": self.rolling_p50_ms,
            "samples": self.samples,
            "max_p50_ms": self.max_p50_ms,
        }


class ANEHealthGate:
    def __init__(
        self,
        *,
        available: bool,
        max_p50_ms: float = 125.0,
        window_size: int = 32,
        min_runtime_samples: int = 16,
    ):
        if max_p50_ms <= 0:
            raise ValueError("max_p50_ms must be positive")
        if window_size < 1 or min_runtime_samples < 1:
            raise ValueError("window sizes must be positive")
        if min_runtime_samples > window_size:
            raise ValueError("min_runtime_samples cannot exceed window_size")

        self.max_p50_ms = float(max_p50_ms)
        self.window_size = window_size
        self.min_runtime_samples = min_runtime_samples
        self._latencies: deque[float] = deque(maxlen=window_size)
        self._state: HealthState = "unknown" if available else "unavailable"
        self._reason = "startup_probe_required" if available else "ane_not_configured"

    def _p50(self) -> float | None:
        if not self._latencies:
            return None
        return float(statistics.median(self._latencies))

    def snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            state=self._state,
            reason=self._reason,
            rolling_p50_ms=self._p50(),
            samples=len(self._latencies),
            max_p50_ms=self.max_p50_ms,
        )

    def mark_startup_probe(
        self,
        *,
        selected_agreement: bool,
        latencies_ms: list[float],
    ) -> HealthSnapshot:
        self._latencies.clear()
        self._latencies.extend(float(value) for value in latencies_ms)
        p50 = self._p50()
        if not selected_agreement:
            self._state = "degraded"
            self._reason = "startup_decision_mismatch"
        elif p50 is None:
            self._state = "degraded"
            self._reason = "startup_probe_empty"
        elif p50 > self.max_p50_ms:
            self._state = "degraded"
            self._reason = "startup_latency_degraded"
        else:
            self._state = "healthy"
            self._reason = "startup_probe_passed"
        return self.snapshot()

    def record_success(self, latency_ms: float) -> HealthSnapshot:
        if self._state == "unavailable":
            return self.snapshot()
        self._latencies.append(float(latency_ms))
        if len(self._latencies) >= self.min_runtime_samples:
            p50 = self._p50()
            if p50 is not None and p50 > self.max_p50_ms:
                self._state = "degraded"
                self._reason = "runtime_latency_degraded"
        return self.snapshot()

    def record_failure(self, reason: str = "runtime_failure") -> HealthSnapshot:
        if self._state != "unavailable":
            self._state = "degraded"
            self._reason = reason
        return self.snapshot()
