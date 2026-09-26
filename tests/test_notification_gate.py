from __future__ import annotations

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.router import DecisionRouter
from local_system_one.workflows.notification_gate import (
    NotificationGate,
    NotificationGateRequest,
)


class FakeRuntime:
    name = "mlx"

    def __init__(self, score: float):
        self.score = score
        self.predict_calls = 0

    def token_count(self, state, question):
        return 210

    def predict(self, state, question):
        self.predict_calls += 1
        low = max(0.0, 1.0 - self.score / 4.0)
        high = 1.0 - low
        return {
            "type": "score",
            "score": self.score,
            "probabilities": {
                "0": low * 0.6,
                "1": low * 0.4,
                "2": 0.0,
                "3": high * 0.4,
                "4": high * 0.6,
            },
            "confidence": 0.8,
            "action": {"act_probability": 1.0},
        }


def make_gate(score: float) -> tuple[NotificationGate, FakeRuntime]:
    runtime = FakeRuntime(score)
    engine = DecisionEngine(
        mlx=runtime,
        ane=None,
        router=DecisionRouter(),
        health=ANEHealthGate(available=False),
    )
    return NotificationGate(engine), runtime


def test_critical_is_immediate_notification():
    gate, runtime = make_gate(0.0)
    result = gate.decide(
        NotificationGateRequest(event="Production service is down.", urgency="critical")
    )
    assert result["delivery"] == "notify_now"
    assert result["reason"] == "urgency_critical"
    assert runtime.predict_calls == 0


def test_blocking_failure_is_immediate_notification():
    gate, runtime = make_gate(0.0)
    result = gate.decide(
        NotificationGateRequest(
            event="Agent cannot continue without user credentials.",
            blocking_failure=True,
        )
    )
    assert result["delivery"] == "notify_now"
    assert result["reason"] == "blocking_failure"
    assert runtime.predict_calls == 0


def test_routine_update_goes_to_digest():
    gate, runtime = make_gate(4.0)
    result = gate.decide(
        NotificationGateRequest(
            event="Nightly backup completed successfully.",
            routine_update=True,
            urgency="low",
        )
    )
    assert result["delivery"] == "digest"
    assert result["reason"] == "routine_update"
    assert runtime.predict_calls == 0


def test_low_model_priority_is_silent():
    gate, runtime = make_gate(0.8)
    result = gate.decide(
        NotificationGateRequest(event="Minor background state changed.")
    )
    assert result["delivery"] == "silent"
    assert result["decision_source"] == "model"
    assert runtime.predict_calls == 1


def test_medium_model_priority_goes_to_digest():
    gate, _runtime = make_gate(2.0)
    result = gate.decide(
        NotificationGateRequest(event="Useful progress update available.")
    )
    assert result["delivery"] == "digest"
    assert result["decision_source"] == "model"


def test_high_model_priority_notifies_now():
    gate, _runtime = make_gate(3.2)
    result = gate.decide(
        NotificationGateRequest(event="Important issue requires attention.")
    )
    assert result["delivery"] == "notify_now"
    assert result["decision_source"] == "model"