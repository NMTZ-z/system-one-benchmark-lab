from __future__ import annotations

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.router import DecisionRouter
from local_system_one.workflows.model_tier_gate import ModelTierGate, ModelTierRequest


class FakeRuntime:
    name = "mlx"

    def __init__(self, score: float):
        self.score = score
        self.predict_calls = 0

    def token_count(self, state, question):
        return 240

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
            "confidence": 0.7,
            "action": {"act_probability": 1.0},
        }


def make_gate(score: float) -> tuple[ModelTierGate, FakeRuntime]:
    runtime = FakeRuntime(score)
    engine = DecisionEngine(
        mlx=runtime,
        ane=None,
        router=DecisionRouter(),
        health=ANEHealthGate(available=False),
    )
    return ModelTierGate(engine), runtime


def test_high_risk_is_hard_strong():
    gate, runtime = make_gate(0.0)
    result = gate.decide(
        ModelTierRequest(task="Modify production access policy.", risk="high")
    )
    assert result["tier"] == "strong"
    assert result["decision_source"] == "rule"
    assert result["reason"] == "risk_high"
    assert runtime.predict_calls == 0


def test_irreversible_is_hard_strong():
    gate, runtime = make_gate(0.0)
    result = gate.decide(
        ModelTierRequest(task="Delete the remote resource.", irreversible=True)
    )
    assert result["tier"] == "strong"
    assert result["reason"] == "irreversible_action"
    assert runtime.predict_calls == 0


def test_bounded_transform_is_hard_fast():
    gate, runtime = make_gate(4.0)
    result = gate.decide(
        ModelTierRequest(
            task="润色下面这段话。",
            context={"text": "测试文本"},
            risk="low",
            task_type="transform",
        )
    )
    assert result["tier"] == "fast"
    assert result["reason"] == "bounded_transform"
    assert runtime.predict_calls == 0


def test_low_model_score_uses_fast():
    gate, runtime = make_gate(1.2)
    result = gate.decide(ModelTierRequest(task="Explain a familiar concept."))
    assert result["tier"] == "fast"
    assert result["decision_source"] == "model"
    assert result["reason"] == "model_complexity_fast_sufficient"
    assert runtime.predict_calls == 1


def test_high_model_score_uses_strong():
    gate, runtime = make_gate(3.1)
    result = gate.decide(ModelTierRequest(task="Analyze a complex architecture."))
    assert result["tier"] == "strong"
    assert result["decision_source"] == "model"
    assert result["reason"] == "model_complexity_requires_strong"
    assert runtime.predict_calls == 1
