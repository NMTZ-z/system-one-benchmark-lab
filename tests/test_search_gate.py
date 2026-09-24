from __future__ import annotations

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.router import DecisionRouter
from local_system_one.workflows.search_gate import SearchGate, SearchGateRequest


class FakeRuntime:
    name = "mlx"

    def __init__(self, probability_true: float = 0.2):
        self.probability_true = probability_true
        self.predict_calls = 0

    def token_count(self, state, question):
        return 220

    def predict(self, state, question):
        self.predict_calls += 1
        return {
            "type": "noul",
            "noul": self.probability_true,
            "confidence": abs(self.probability_true - 0.5) * 2.0,
            "action": {"act_probability": 1.0},
        }


def make_gate(probability_true: float = 0.2) -> tuple[SearchGate, FakeRuntime]:
    runtime = FakeRuntime(probability_true)
    engine = DecisionEngine(
        mlx=runtime,
        ane=None,
        router=DecisionRouter(),
        health=ANEHealthGate(available=False),
    )
    return SearchGate(engine), runtime


def test_current_freshness_is_hard_search():
    gate, runtime = make_gate()
    result = gate.decide(
        SearchGateRequest(
            task="Who is the current CEO of this company?",
            freshness="current",
        )
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "freshness_current"
    assert runtime.predict_calls == 0


def test_provided_only_is_hard_no_search():
    gate, runtime = make_gate(probability_true=0.95)
    result = gate.decide(
        SearchGateRequest(
            task="Rewrite this paragraph more clearly.",
            source_scope="provided_only",
            context={"text": "hello"},
        )
    )
    assert result["should_search"] is False
    assert result["decision_source"] == "rule"
    assert runtime.predict_calls == 0


def test_current_language_is_search_without_hint():
    gate, runtime = make_gate()
    result = gate.decide(SearchGateRequest(task="今天北京天气怎么样？"))
    assert result["should_search"] is True
    assert result["reason"] == "current_language"
    assert runtime.predict_calls == 0


def test_model_confident_no_search():
    gate, runtime = make_gate(probability_true=0.2)
    result = gate.decide(
        SearchGateRequest(task="Explain the difference between a list and a tuple.")
    )
    assert result["should_search"] is False
    assert result["decision_source"] == "model"
    assert result["reason"] == "model_confident_local_answer"
    assert runtime.predict_calls == 1


def test_model_uncertainty_searches_conservatively():
    gate, runtime = make_gate(probability_true=0.45)
    result = gate.decide(
        SearchGateRequest(task="Tell me about a named product that may have changed.")
    )
    assert result["should_search"] is True
    assert result["decision_source"] == "model"
    assert result["reason"] == "model_uncertain_conservative_search"
    assert runtime.predict_calls == 1


def test_volatile_named_role_is_hard_search_without_current_word():
    gate, runtime = make_gate(probability_true=0.01)
    result = gate.decide(SearchGateRequest(task="OpenAI 的 CEO 是谁？"))
    assert result["should_search"] is True
    assert result["decision_source"] == "rule"
    assert result["reason"] == "volatile_public_fact"
    assert runtime.predict_calls == 0
