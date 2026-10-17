"""Model Backend Pilot: strict protocol, Laya parity, Jev Mock and gate safety."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_system_one.engine import DecisionEngine
from local_system_one.health import ANEHealthGate
from local_system_one.model_backends.contract import (
    ModelContractError, TypedRequest, TypedResult, UnsupportedCapability,
)
from local_system_one.model_backends.jev import (
    BudgetExhausted, JEVProvider, RemoteDisabled, VersionDrift, parse_response,
)
from local_system_one.model_backends.laya import LayaProvider, ResearchEngine
from local_system_one.router import DecisionRouter
from local_system_one.schemas import DecisionRequest
from local_system_one.workflows.completion_gate import CompletionGate, CompletionGateRequest
from local_system_one.workflows.retry_escalation_gate import RetryEscalationGate, RetryEscalationRequest
from benchmarks.model_backend_pilot.__main__ import _records, main


def choice(**patch):
    data = {
        "primitive": "choice", "state": {"outcome": "ok"},
        "instructions": "Choose the safest response.",
        "criteria": ["complete", "verify", "continue"],
        "request_id": "pilot-t1",
    }
    data.update(patch)
    return TypedRequest(**data)


def score():
    return TypedRequest("score", "Low-to-medium impact", "Assess severity",
                        ["No impact", "Minor impact", "Major impact"], "s1")


def noul():
    return TypedRequest("noul", "Tests failed", "Are tests failing?", None, "n1")


def response(request, *, selected=None, probabilities=None, model="jev-1.13.0"):
    if request.primitive == "choice":
        answer = {"type": "choice", "choice": selected or "continue",
                  "probabilities": probabilities or {
                      "complete": .1, "verify": .2, "continue": .7,
                  }, "confidence": .75}
    elif request.primitive == "score":
        answer = {"type": "score", "score": 1.05, "legend": {
            "0": "No impact", "1": "Minor impact", "2": "Major impact"},
            "probabilities": {"0": 0, "1": .95, "2": .05}, "confidence": .92}
    else:
        answer = {"type": "noul", "noul": .95}
    return {"model": model, "answers": {"decision": answer},
            "usage": {"input_tokens": 89, "output_tokens": 9}}


@pytest.mark.parametrize("typed_request", [choice(), score(), noul()])
def test_jev_parser_real_wire_shape(typed_request):
    parsed = parse_response(json.dumps(response(typed_request)).encode(), typed_request, "jev-1.13.0", 5.0)
    assert parsed.provider_id == "jev"
    assert parsed.model_resolved == "jev-1.13.0"
    assert parsed.usage["input_tokens"] == 89
    assert parsed.execution_backend == "remote_http"
    assert parsed.request_id == typed_request.request_id
    if typed_request.primitive == "noul":
        assert parsed.decision is True
        assert parsed.provider_confidence is None


def test_choice_list_translates_to_map_without_reordering():
    req = choice()
    assert list(req.to_question()["criteria"]) == ["complete", "verify", "continue"]
    assert list(req.to_question()["criteria"].values()) == [None, None, None]
    described = choice(criteria={"verify": "Need evidence", "complete": "All good"})
    assert described.to_question()["criteria"] == {"verify": "Need evidence", "complete": "All good"}


@pytest.mark.parametrize("request_data,kind", [
    ({"criteria": ["a", "a"]}, ModelContractError),
    ({"criteria": ["one"]}, ModelContractError),
    ({"criteria": [0, 1]}, ModelContractError),
    ({"state": {"bad": float("nan")}}, ModelContractError),
    ({"request_id": "x" * 129}, ModelContractError),
    ({"primitive": "unknown"}, UnsupportedCapability),
])
def test_bad_requests_rejected(request_data, kind):
    with pytest.raises(kind):
        choice(**request_data)


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(model="jev-1.14.0"),
    lambda r: r.update(answers={"other": {"type": "noul", "noul": .9}}),
    lambda r: r["answers"]["decision"].update(type="noul"),
    lambda r: r["answers"]["decision"].update(choice="unknown"),
    lambda r: r["answers"]["decision"].update(choice="complete"),
    lambda r: r["answers"]["decision"].update(probabilities={"complete": .3, "verify": .2}),
    lambda r: r["answers"]["decision"].update(probabilities={"complete": .1, "verify": .2, "continue": .8}),
    lambda r: r["answers"]["decision"].update(probabilities={"complete": float("nan"), "verify": .2, "continue": .8}),
    lambda r: r["answers"]["decision"].update(confidence=2),
    lambda r: r.update(usage={"input_tokens": True, "output_tokens": 5}),
])
def test_malformed_jev_rejected(mutation):
    req = choice()
    record = response(req)
    mutation(record)
    with pytest.raises((ModelContractError, VersionDrift)):
        parse_response(json.dumps(record).encode(), req, "jev-1.13.0", 3)


def test_score_legend_and_weighted_value_are_checked():
    req = score()
    record = response(req)
    record["answers"]["decision"]["legend"]["1"] = "Different rubric"
    with pytest.raises(ModelContractError):
        parse_response(json.dumps(record).encode(), req, "jev-1.13.0", 5)
    record = response(req)
    record["answers"]["decision"]["score"] = 1.5
    with pytest.raises(ModelContractError):
        parse_response(json.dumps(record).encode(), req, "jev-1.13.0", 5)


def test_choice_tie_does_not_fake_unique_argmax():
    req = choice()
    record = response(req, selected="verify",
                      probabilities={"complete": .45, "verify": .45, "continue": .1})
    out = parse_response(json.dumps(record).encode(), req, "jev-1.13.0", 5)
    assert out.decision == "verify"


def test_response_rejects_duplicated_json_keys_and_overlarge_numbers():
    req = choice()
    raw = b'{"model":"jev-1.13.0","model":"jev-1.13.0","answers":{}}'
    with pytest.raises(ModelContractError):
        parse_response(raw, req, "jev-1.13.0", 5)
    raw = b'{"model":"jev-1.13.0","answers":{"decision":{"type":"choice","choice":"complete","probabilities":{"complete":1e400,"verify":0,"continue":0}}}}'
    with pytest.raises(ModelContractError):
        parse_response(raw, req, "jev-1.13.0", 5)


def test_remote_off_default_and_no_implicit_key_lookup(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-secret-not-real")
    calls = []
    client = JEVProvider(transport=lambda *args: calls.append(args))
    with pytest.raises(RemoteDisabled):
        client.evaluate(choice())
    assert calls == [] and client.attempts == 0


def test_remote_requires_key_without_calling_transport(monkeypatch):
    # A developer's real macOS Keychain may have a configured credential.
    # Isolate this negative test from the host Keychain without ever reading it.
    monkeypatch.setattr("local_system_one.model_backends.jev._load_api_key", lambda: None)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    calls = []
    client = JEVProvider(
        allow_remote=True, public_data_confirmed=True, max_requests=1,
        max_total_usd=.001, transport=lambda *args: calls.append(args)
    )
    with pytest.raises(RemoteDisabled):
        client.evaluate(choice())
    assert not calls and client.attempts == 0


def test_one_mock_http_call_pinned_model_budget_and_redaction(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-secret-not-real")
    calls = []

    def transport(req, timeout, limit):
        calls.append((req.full_url, req.data, req.headers.get("Authorization"), timeout, limit))
        return json.dumps(response(choice())).encode()

    client = JEVProvider(
        allow_remote=True, public_data_confirmed=True, max_requests=1,
        max_total_usd=.001, transport=transport,
    )
    result = client.evaluate(choice())
    assert result.decision == "continue"
    assert len(calls) == 1 and calls[0][0] == "https://api.typesafe.ai/v1/systemone"
    assert json.loads(calls[0][1])["model"] == "jev-1.13.0"
    assert client.measured_usd > 0
    with pytest.raises(BudgetExhausted):
        client.evaluate(choice())
    assert client.attempts == 1
    with pytest.raises(ValueError):
        JEVProvider(model="jev-latest")


def test_remote_transport_failure_is_not_retried(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-secret-not-real")
    calls = []

    def fails(*args):
        calls.append(1)
        raise TimeoutError("no transport")

    client = JEVProvider(
        allow_remote=True, public_data_confirmed=True, max_requests=2,
        max_total_usd=.002, transport=fails,
    )
    with pytest.raises(TimeoutError):
        client.evaluate(choice())
    assert len(calls) == 1 and client.attempts == 1


class FakeRuntime:
    name = "mlx"

    def __init__(self, answer=None):
        self.answer = answer or {
            "type": "choice", "choice": "complete",
            "probabilities": {"complete": .9, "verify": .05, "continue": .05},
            "confidence": .8, "action": {"act_probability": .15},
        }
        self.calls = 0
        self.last_question = None

    def token_count(self, state, question):
        self.last_question = question
        return 40

    def predict(self, state, question):
        self.calls += 1
        return self.answer


def make_laya():
    runtime = FakeRuntime()
    engine = DecisionEngine(mlx=runtime, ane=None,
                            router=DecisionRouter(), health=ANEHealthGate(available=False))
    return engine, runtime


def test_laya_wrap_raw_decisions_no_mlx_import_or_semantic_change():
    engine, runtime = make_laya()
    legacy_request = DecisionRequest(
        primitive="choice", state="all done", instructions="Is it complete?",
        criteria=["complete", "verify", "continue"], request_id="pilot-t1"
    )
    before = engine.decide(legacy_request)
    provider = LayaProvider(engine, model_identity="test-pinned-checkpoint")
    wrapped = provider.evaluate(choice(state="all done", instructions="Is it complete?"))
    assert wrapped.decision == before["decision"]
    assert wrapped.probabilities == before["probabilities"]
    assert wrapped.execution_backend == before["backend"]
    assert wrapped.extensions["legacy_token_count"] == before["token_count"]
    assert runtime.last_question["criteria"] == ["complete", "verify", "continue"]
    assert runtime.calls == 2
    assert wrapped.provider_confidence is None  # Do not rebrand legacy field.


def test_gate_rule_safety_is_shared_and_skips_both_backends(monkeypatch):
    engine, runtime = make_laya()
    laya = ResearchEngine(LayaProvider(engine, model_identity="frozen"))
    completion = CompletionGateRequest.from_payload({
        "task": "Validate report", "current_result": "Validation failed",
        "execution_state": {"tests_run": 3, "tests_passed": 2}, "request_id": "safe",
    })
    a = CompletionGate(laya).decide(completion)
    assert a["decision"] == "continue" and runtime.calls == 0
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-secret-not-real")
    calls = []
    jev = ResearchEngine(JEVProvider(
        allow_remote=True, public_data_confirmed=True, max_requests=1,
        max_total_usd=.001, transport=lambda *args: calls.append(1),
    ))
    b = CompletionGate(jev).decide(completion)
    assert b["decision"] == a["decision"] and b["reason"] == a["reason"]
    assert not calls


def test_gate_model_path_reuses_policy_not_new_jev_threshold(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-secret-not-real")
    request = CompletionGateRequest.from_payload({
        "task": "Deliver report", "current_result": "Report checked",
        "execution_state": {"required_checks_completed": True}, "request_id": "safe",
    })
    typed = choice(criteria=["complete", "verify", "continue"], request_id="safe")
    wire = response(typed, selected="complete",
                    probabilities={"complete": .65, "verify": .25, "continue": .1})

    def transport(req, timeout, limit):
        return json.dumps(wire).encode()

    client = ResearchEngine(JEVProvider(
        allow_remote=True, public_data_confirmed=True, max_requests=1,
        max_total_usd=.001, transport=transport,
    ))
    result = CompletionGate(client).decide(request)
    assert result["decision"] == "verify"  # Shared 0.70 experiment, not Jev calibration.
    assert result["reason"] == "model_complete_below_safety_threshold"
    assert client.last_result.model_requested == "jev-1.13.0"


def test_research_cli_remote_blocked_and_rule_baseline(tmp_path):
    dataset = Path(__file__).resolve().parents[1] / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"
    assert main(["run", "--provider", "jev", "--dataset", str(dataset),
                 "--output", str(tmp_path / "jev.json")]) == 3
    assert not (tmp_path / "jev.json").exists()
    rule_out = tmp_path / "rule.json"
    assert main(["run", "--provider", "rule", "--dataset", str(dataset),
                 "--output", str(rule_out)]) == 2  # primitive cases unsupported
    report = json.loads(rule_out.read_text())
    assert report["summary"]["total"] == 12
    assert report["remote_attempts"] == 0
    assert report["cases"][0]["status"] == "unsupported"


def test_comparison_rejects_incomplete_or_fake_jev(tmp_path):
    dataset = Path(__file__).resolve().parents[1] / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"
    hash_, rows = _records(dataset)
    assert hash_ and len(rows) == 12
    p = tmp_path / "r.json"
    assert main(["run", "--provider", "rule", "--dataset", str(dataset),
                 "--output", str(p)]) == 2
    report = json.loads(p.read_text())
    # This synthetic forgery copies the Rule-only unsupported primitive rows
    # into supposedly model-backed Laya/Jev reports. Reject that impossible
    # provider/status combination before looking for Jev live-call evidence.
    report["code_checkout_clean_at_run"] = True
    p.write_text(json.dumps(report))
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for path, provider in ((a, "laya"), (b, "jev")):
        fake = {
            **report, "provider": provider, "code_checkout_clean_at_run": True,
            "requested_model": (
                "synthetic-local-checkpoint" if provider == "laya" else "jev-1.13.0"
            ),
        }
        path.write_text(json.dumps(fake))
    with pytest.raises(ValueError, match="laya provider cannot report unsupported status"):
        from benchmarks.model_backend_pilot.__main__ import compare
        from argparse import Namespace
        compare(Namespace(reports=[p, a, b], output=tmp_path / "compare.json"))
