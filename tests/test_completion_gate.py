from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from local_system_one.health import ANEHealthGate
from local_system_one.metrics import ServiceMetrics
from local_system_one.service import create_server
from local_system_one.workflows.completion_gate import (
    MAX_RESULT_CHARS,
    MAX_TASK_CHARS,
    CompletionGate,
    CompletionGateRequest,
)


class FakeEngine:
    def __init__(self, *, decision: str = "complete", probability: float = 0.9, fail: bool = False):
        self.metrics = ServiceMetrics()
        self.health = ANEHealthGate(available=False)
        self.decision = decision
        self.probability = probability
        self.fail = fail
        self.calls = 0
        self.last_request = None

    def decide(self, request):
        self.calls += 1
        self.last_request = request
        if self.fail:
            raise RuntimeError("synthetic model failure")
        probabilities = {"complete": 0.05, "verify": 0.05, "continue": 0.05}
        probabilities[self.decision] = self.probability
        return {
            "decision": self.decision,
            "probabilities": probabilities,
            "confidence": self.probability,
            "backend": "mlx",
            "route_reason": "short_input",
            "token_count": 120,
            "latency_ms": 5.0,
        }

    def health_snapshot(self):
        return {"service": "ok", "ane": self.health.snapshot().as_dict()}

    def metrics_snapshot(self):
        return self.metrics.snapshot()


def request(**state):
    return CompletionGateRequest.from_payload(
        {
            "task": "Create the requested report and validate it.",
            "current_result": "Report created and all required checks passed.",
            "execution_state": state,
            "request_id": "completion-test",
        }
    )


def test_model_complete_case():
    engine = FakeEngine(decision="complete", probability=0.91)
    result = CompletionGate(engine).decide(request(required_checks_completed=True))
    assert result["decision"] == "complete"
    assert result["decision_source"] == "model"
    assert result["probability_complete"] == pytest.approx(0.91)
    assert engine.calls == 1
    assert engine.last_request.question()["criteria"] == {
        "complete": "the requested task is satisfied and important checks are complete",
        "verify": "a candidate result exists but important independent validation is missing",
        "continue": "substantive requested work is missing, failed, or still in progress",
    }


def test_hard_continue_skips_model_for_failed_required_test():
    engine = FakeEngine()
    result = CompletionGate(engine).decide(request(tests_run=3, tests_passed=2))
    assert result["decision"] == "continue"
    assert result["decision_source"] == "rule"
    assert result["reason"] == "explicit_test_failure"
    assert engine.calls == 0


def test_hard_verify_skips_model_for_unverified_final_state():
    engine = FakeEngine()
    result = CompletionGate(engine).decide(
        request(verification_required=True, final_state_verified=False)
    )
    assert result["decision"] == "verify"
    assert result["reason"] == "final_state_not_verified"
    assert engine.calls == 0


def test_low_confidence_model_complete_is_downgraded_to_verify():
    engine = FakeEngine(decision="complete", probability=0.65)
    result = CompletionGate(engine).decide(request())
    assert result["decision"] == "verify"
    assert result["reason"] == "model_complete_below_safety_threshold"


def test_model_failure_fails_safe_to_continue():
    engine = FakeEngine(fail=True)
    result = CompletionGate(engine).decide(request())
    assert result["decision"] == "continue"
    assert result["reason"] == "model_failure_fail_open_continue"


def test_request_rejects_missing_unknown_and_invalid_fields():
    with pytest.raises(ValueError, match="task must be a non-empty string"):
        CompletionGateRequest.from_payload(
            {"current_result": "x", "execution_state": {}}
        )
    with pytest.raises(ValueError, match="unknown completion request"):
        CompletionGateRequest.from_payload(
            {"task": "x", "current_result": "y", "execution_state": {}, "transcript": "no"}
        )
    with pytest.raises(TypeError, match="tests_run"):
        CompletionGateRequest.from_payload(
            {"task": "x", "current_result": "y", "execution_state": {"tests_run": -1}}
        )


def test_input_is_bounded_without_persisting_raw_transcript_shape():
    value = CompletionGateRequest.from_payload(
        {
            "task": "t" * (MAX_TASK_CHARS + 200),
            "current_result": "r" * (MAX_RESULT_CHARS + 200),
            "execution_state": {"tools_used": 2},
            "request_id": "bounded",
        }
    )
    assert len(value.task) == MAX_TASK_CHARS
    assert len(value.current_result) == MAX_RESULT_CHARS
    assert value.task_truncated is True
    assert value.result_truncated is True


def _post_json(url: str, payload: dict) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_runtime_endpoint_accepts_valid_and_rejects_malformed_requests():
    engine = FakeEngine(decision="complete", probability=0.95)
    server = create_server(engine, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}/v1/workflows/completion-gate"
        status, value = _post_json(
            base,
            {
                "task": "Confirm the deployment.",
                "current_result": "Deployment verified healthy.",
                "execution_state": {"required_checks_completed": True},
                "request_id": "http-valid",
            },
        )
        assert status == 200
        assert value["workflow"] == "completion_gate"
        assert value["decision"] == "complete"

        status, value = _post_json(base, {"task": "missing fields"})
        assert status == 400
        assert value["error"] == "invalid_request"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
