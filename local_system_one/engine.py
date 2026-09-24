"""Decision engine combining MLX fallback, L512 ANE and health-aware routing."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from .health import ANEHealthGate
from .metrics import ServiceMetrics
from .probes import PROBES
from .router import DecisionRouter
from .runtime.base import DecisionRuntime
from .schemas import DecisionRequest, normalized_answer, selected_label


class DecisionEngine:
    def __init__(
        self,
        *,
        mlx: DecisionRuntime,
        ane: DecisionRuntime | None,
        router: DecisionRouter,
        health: ANEHealthGate,
        metrics: ServiceMetrics | None = None,
    ):
        self.mlx = mlx
        self.ane = ane
        self.router = router
        self.health = health
        self.metrics = metrics or ServiceMetrics()
        self._lock = Lock()

    def startup_probe(self, *, repeats: int = 2) -> dict[str, Any]:
        if self.ane is None:
            return self.health.snapshot().as_dict()

        reference = []
        for state, question in PROBES:
            reference.append(selected_label(self.mlx.predict(state, question)))

        latencies: list[float] = []
        agreements = []
        for _ in range(repeats):
            for (state, question), expected in zip(PROBES, reference):
                started = time.perf_counter()
                answer = self.ane.predict(state, question)
                latencies.append((time.perf_counter() - started) * 1000.0)
                agreements.append(selected_label(answer) == expected)

        return self.health.mark_startup_probe(
            selected_agreement=all(agreements),
            latencies_ms=latencies,
        ).as_dict()

    def decide(self, request: DecisionRequest) -> dict[str, Any]:
        question = request.question()
        token_count = self.mlx.token_count(request.state, question)
        snapshot = self.health.snapshot()
        route = self.router.route(
            token_count,
            ane_healthy=snapshot.healthy,
            ane_available=self.ane is not None,
            override=request.backend,
        )

        backend_name = route.backend
        route_reason = route.reason
        runtime = self.mlx if route.backend == "mlx" else self.ane
        if runtime is None:
            raise RuntimeError("selected backend is unavailable")

        started = time.perf_counter()
        try:
            with self._lock:
                answer = runtime.predict(request.state, question)
            latency_ms = (time.perf_counter() - started) * 1000.0
        except Exception:
            if route.backend != "ane":
                self.metrics.record_error()
                raise
            self.health.record_failure("ane_runtime_failure")
            backend_name = "mlx"
            route_reason = "ane_failure_fallback"
            started = time.perf_counter()
            with self._lock:
                answer = self.mlx.predict(request.state, question)
            latency_ms = (time.perf_counter() - started) * 1000.0

        if backend_name == "ane":
            self.health.record_success(latency_ms)

        self.metrics.record(
            backend=backend_name,
            route_reason=route_reason,
            latency_ms=latency_ms,
        )

        result = normalized_answer(answer)
        result.update(
            {
                "primitive": request.primitive,
                "backend": backend_name,
                "route_reason": route_reason,
                "token_count": token_count,
                "latency_ms": latency_ms,
                "request_id": request.request_id,
                "ane_health": self.health.snapshot().as_dict(),
            }
        )
        return result

    def health_snapshot(self) -> dict[str, Any]:
        return {
            "service": "ok",
            "ane": self.health.snapshot().as_dict(),
        }

    def metrics_snapshot(self) -> dict[str, Any]:
        return self.metrics.snapshot()
