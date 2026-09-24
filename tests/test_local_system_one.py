from __future__ import annotations

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.router import DecisionRouter, RouterConfig
from local_system_one.schemas import DecisionRequest


class FakeRuntime:
    def __init__(self, name: str, token_count: int, answer: dict, fail: bool = False):
        self.name = name
        self._token_count = token_count
        self.answer = answer
        self.fail = fail
        self.calls = 0

    def token_count(self, state, question):
        return self._token_count

    def predict(self, state, question):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return self.answer


CHOICE = {
    "type": "choice",
    "choice": "billing",
    "probabilities": {"billing": 0.9, "other": 0.1},
    "confidence": 0.8,
    "action": {"act_probability": 0.2},
}


def test_request_validation_and_question():
    request = DecisionRequest.from_payload(
        "choice",
        {
            "state": {"subject": "invoice"},
            "instructions": "Route this.",
            "options": ["billing", "other"],
        },
    )
    assert request.question()["type"] == "choice"
    assert request.question()["criteria"] == ["billing", "other"]


def test_router_short_medium_long_and_unhealthy():
    router = DecisionRouter(RouterConfig(ane_min_tokens=192, ane_max_tokens=512))
    assert (
        router.route(100, ane_healthy=True, ane_available=True).reason == "short_input"
    )
    assert router.route(300, ane_healthy=True, ane_available=True).backend == "ane"
    assert (
        router.route(600, ane_healthy=True, ane_available=True).reason
        == "over_ane_capacity"
    )
    assert (
        router.route(300, ane_healthy=False, ane_available=True).reason
        == "ane_unhealthy"
    )


def test_health_gate_degrades_on_latency():
    health = ANEHealthGate(
        available=True,
        max_p50_ms=100,
        window_size=4,
        min_runtime_samples=4,
    )
    health.mark_startup_probe(selected_agreement=True, latencies_ms=[80, 90])
    assert health.snapshot().healthy
    for value in [130, 140, 150, 160]:
        health.record_success(value)
    assert health.snapshot().state == "degraded"


def test_engine_routes_to_ane_when_healthy():
    mlx = FakeRuntime("mlx", 300, CHOICE)
    ane = FakeRuntime("ane_l512", 300, CHOICE)
    health = ANEHealthGate(available=True, max_p50_ms=1000)
    health.mark_startup_probe(selected_agreement=True, latencies_ms=[10])
    engine = DecisionEngine(
        mlx=mlx,
        ane=ane,
        router=DecisionRouter(),
        health=health,
    )
    request = DecisionRequest.from_payload(
        "choice",
        {
            "state": {"subject": "invoice"},
            "instructions": "Route.",
            "criteria": ["billing", "other"],
        },
    )
    result = engine.decide(request)
    assert result["backend"] == "ane"
    assert result["decision"] == "billing"
    assert result["route_reason"] == "ane_suitable"


def test_engine_falls_back_after_ane_failure():
    mlx = FakeRuntime("mlx", 300, CHOICE)
    ane = FakeRuntime("ane_l512", 300, CHOICE, fail=True)
    health = ANEHealthGate(available=True, max_p50_ms=1000)
    health.mark_startup_probe(selected_agreement=True, latencies_ms=[10])
    engine = DecisionEngine(
        mlx=mlx,
        ane=ane,
        router=DecisionRouter(),
        health=health,
    )
    request = DecisionRequest.from_payload(
        "choice",
        {
            "state": {},
            "instructions": "Route.",
            "criteria": ["billing", "other"],
        },
    )
    result = engine.decide(request)
    assert result["backend"] == "mlx"
    assert result["route_reason"] == "ane_failure_fallback"
    assert health.snapshot().state == "degraded"
    assert mlx.calls == 1
    assert ane.calls == 1
