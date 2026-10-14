from __future__ import annotations

import json
from pathlib import Path

import pytest

from local_system_one.adapter_contract import (
    ADAPTER_CONTRACT_VERSION,
    ActionOutcome,
    AdapterContractError,
    envelope_from_runtime,
    validate_decision_envelope,
)


def search_envelope():
    return {
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "request_id": "turn-1",
        "gate": "search",
        "decision": {"value": "no_search", "probability_search": 0.0},
        "decision_source": "rule",
        "reason": "local_file_or_repo",
        "backend": "rule",
        "latency_ms": 0.0,
        "confidence": 1.0,
        "metadata": {"future_adapter_field": "allowed"},
    }



def _valid_retry_envelope():
    value = search_envelope()
    value["gate"] = "retry_escalation"
    value["decision"] = {
        "value": "verify_state",
        "raw_model_decision": None,
        "safety_override_reason": None,
    }
    return value


def _valid_retry_runtime():
    return {
        "workflow": "retry_escalation_gate",
        "decision": "verify_state", "guarded_decision": "verify_state",
        "raw_model_decision": None, "safety_override_reason": None,
        "decision_source": "rule", "reason": "unconfirmed_side_effect_verify_first",
        "backend": "rule", "latency_ms": 0.25, "confidence": 1.0,
        "request_id": "strict-nullable-test", "advisory_only": True,
    }


@pytest.mark.parametrize("missing", ["request_id"])
def test_all_gate_envelopes_reject_missing_required_nullable_top_level(missing):
    for gate in ("search", "model_tier", "notification", "completion", "retry_escalation"):
        # This checks top-level presence before per-gate content validation.
        value = search_envelope()
        value["gate"] = gate
        del value[missing]
        with pytest.raises(AdapterContractError, match="missing decision envelope field"):
            validate_decision_envelope(value)


@pytest.mark.parametrize("field", ["confidence", "metadata"])
def test_optional_contract_fields_do_not_accept_explicit_null(field):
    value = search_envelope()
    value[field] = None
    with pytest.raises(AdapterContractError):
        validate_decision_envelope(value)
    del value[field]
    assert validate_decision_envelope(value).gate == "search"


def test_runtime_normalizer_does_not_fabricate_top_level_request_id():
    runtime = _valid_retry_runtime()
    runtime.pop("request_id")
    with pytest.raises(AdapterContractError, match="missing runtime decision field"):
        envelope_from_runtime("retry_escalation", runtime)


def test_runtime_optional_confidence_does_not_fabricate_json_null():
    runtime = _valid_retry_runtime()
    runtime.pop("confidence")
    normalized = envelope_from_runtime("retry_escalation", runtime).as_dict()
    assert "confidence" not in normalized
    runtime["confidence"] = None
    with pytest.raises(AdapterContractError, match="confidence"):
        envelope_from_runtime("retry_escalation", runtime)


@pytest.mark.parametrize("missing", ["value", "raw_model_decision", "safety_override_reason"])
def test_retry_envelope_required_nullable_fields_cannot_be_missing(missing):
    value = _valid_retry_envelope()
    assert validate_decision_envelope(value).decision["raw_model_decision"] is None
    del value["decision"][missing]
    with pytest.raises(AdapterContractError, match="missing Retry decision field"):
        validate_decision_envelope(value)


@pytest.mark.parametrize(
    "missing",
    ["decision", "guarded_decision", "raw_model_decision",
     "safety_override_reason", "advisory_only"],
)
def test_retry_runtime_normalization_never_fabricates_required_fields(missing):
    runtime = _valid_retry_runtime()
    assert envelope_from_runtime("retry_escalation", runtime).metadata["advisory_only"] is True
    del runtime[missing]
    with pytest.raises(AdapterContractError, match="missing Retry runtime field"):
        envelope_from_runtime("retry_escalation", runtime)


@pytest.mark.parametrize("field,value", [
    ("advisory_only", False),
    ("advisory_only", None),
    ("decision", "retry_same"),
    ("raw_model_decision", "unsupported_model"),
    ("safety_override_reason", 99),
])
def test_retry_runtime_normalization_fails_closed_on_wrong_semantics(field, value):
    runtime = _valid_retry_runtime()
    runtime[field] = value
    with pytest.raises(AdapterContractError):
        envelope_from_runtime("retry_escalation", runtime)


def test_retry_contract_json_schema_and_python_agree_on_required_nullable_fields():
    schema = json.loads(
        (Path(__file__).parents[1] / "contracts" / "adapter-contract-v1.schema.json").read_text()
    )
    clauses = schema["$defs"]["decisionEnvelope"]["allOf"]
    gate_clause = next(
        row for row in clauses
        if row["if"]["properties"]["gate"].get("const") == "retry_escalation"
    )
    retry_decision = gate_clause["then"]["properties"]["decision"]
    assert set(retry_decision["required"]) == {
        "value", "raw_model_decision", "safety_override_reason",
    }
    assert retry_decision["properties"]["raw_model_decision"]["type"] == ["string", "null"]
    assert retry_decision["properties"]["safety_override_reason"]["type"] == ["string", "null"]
    assert retry_decision["properties"]["safety_override_reason"]["minLength"] == 1
    assert schema["$defs"]["decisionEnvelope"]["properties"]["request_id"]["minLength"] == 1
    assert validate_decision_envelope(_valid_retry_envelope()).decision == {
        "value": "verify_state", "raw_model_decision": None,
        "safety_override_reason": None,
    }

def test_valid_search_decision_envelope_accepts_unknown_metadata():
    value = validate_decision_envelope(search_envelope())
    assert value.gate == "search"
    assert value.decision["value"] == "no_search"
    assert value.metadata == {"future_adapter_field": "allowed"}


def test_valid_model_tier_decision_envelope():
    value = validate_decision_envelope(
        {
            "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
            "request_id": None,
            "gate": "model_tier",
            "decision": {
                "value": "fast",
                "difficulty_score": 0.0,
                "probability_strong": 0.0,
            },
            "decision_source": "rule",
            "reason": "bounded_transform",
            "backend": "rule",
            "latency_ms": 0.0,
            "confidence": 1.0,
        }
    )
    assert value.decision["value"] == "fast"


def test_malformed_decision_and_unknown_gate_are_rejected():
    malformed = search_envelope()
    malformed["decision"] = {"value": "maybe", "probability_search": 0.0}
    with pytest.raises(AdapterContractError, match="invalid Search decision"):
        validate_decision_envelope(malformed)

    unknown = search_envelope()
    unknown["gate"] = "retry"
    with pytest.raises(AdapterContractError, match="unknown gate"):
        validate_decision_envelope(unknown)


def test_unknown_top_level_field_is_rejected_but_metadata_is_extension_point():
    value = search_envelope()
    value["platform_object"] = {"do_not": "standardize"}
    with pytest.raises(AdapterContractError, match="unknown decision envelope field"):
        validate_decision_envelope(value)

    nested = search_envelope()
    nested["decision"]["reasoning_effort"] = "low"
    with pytest.raises(AdapterContractError, match="unknown Search decision field"):
        validate_decision_envelope(nested)


def test_runtime_search_and_model_tier_responses_normalize_to_same_contract():
    search = envelope_from_runtime(
        "search",
        {
            "workflow": "search_gate",
            "decision": "no_search",
            "decision_source": "rule",
            "reason": "local_file_or_repo",
            "probability_search": 0.0,
            "confidence": 1.0,
            "backend": "rule",
            "route_reason": "search_gate:local_file_or_repo",
            "token_count": 0,
            "latency_ms": 0.0,
            "request_id": "same-turn",
            "ane_health": {"large": "runtime-only metadata is intentionally omitted"},
        },
    )
    tier = envelope_from_runtime(
        "model_tier",
        {
            "workflow": "model_tier_gate",
            "tier": "fast",
            "decision_source": "rule",
            "reason": "bounded_transform",
            "difficulty_score": 0.0,
            "probability_strong": 0.0,
            "confidence": 1.0,
            "backend": "rule",
            "route_reason": "model_tier_gate:bounded_transform",
            "token_count": 0,
            "latency_ms": 0.0,
            "request_id": "same-turn",
        },
    )
    assert search.adapter_contract_version == tier.adapter_contract_version == "1.0"
    assert search.request_id == tier.request_id == "same-turn"
    assert "ane_health" not in (search.metadata or {})


def test_valid_completion_decision_envelope_and_runtime_normalization():
    runtime = {
        "workflow": "completion_gate",
        "decision": "verify",
        "decision_source": "model",
        "reason": "model_verify",
        "probability_complete": 0.2,
        "probability_verify": 0.7,
        "probability_continue": 0.1,
        "confidence": 0.7,
        "backend": "mlx",
        "route_reason": "short_input",
        "token_count": 128,
        "latency_ms": 12.0,
        "request_id": "completion-1",
    }
    value = envelope_from_runtime("completion", runtime)
    assert value.adapter_contract_version == "1.0"
    assert value.gate == "completion"
    assert value.decision == {
        "value": "verify",
        "probability_complete": 0.2,
        "probability_verify": 0.7,
        "probability_continue": 0.1,
    }
    assert value.request_id == "completion-1"


def test_invalid_completion_value_is_rejected():
    value = {
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "request_id": None,
        "gate": "completion",
        "decision": {
            "value": "stop",
            "probability_complete": 1.0,
            "probability_verify": 0.0,
            "probability_continue": 0.0,
        },
        "decision_source": "rule",
        "reason": "invalid-test",
        "backend": "rule",
        "latency_ms": 0.0,
    }
    with pytest.raises(AdapterContractError, match="invalid Completion decision"):
        validate_decision_envelope(value)


def test_action_outcome_has_closed_status_vocabulary():
    assert ActionOutcome("applied", "verified_platform_mapping").as_dict() == {
        "status": "applied",
        "reason": "verified_platform_mapping",
    }
    with pytest.raises(AdapterContractError, match="unsupported action status"):
        ActionOutcome("mutated", "not_part_of_contract")  # type: ignore[arg-type]


def test_machine_readable_schema_has_explicit_root_contract_types():
    schema = json.loads(
        (Path(__file__).parents[1] / "contracts" / "adapter-contract-v1.schema.json").read_text()
    )
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert {entry["$ref"] for entry in schema["oneOf"]} == {
        "#/$defs/decisionEnvelope",
        "#/$defs/actionOutcome",
        "#/$defs/turnContext",
        "#/$defs/gateConfig",
        "#/$defs/telemetry",
    }
    assert schema["$defs"]["decisionEnvelope"]["properties"]["adapter_contract_version"] == {
        "const": "1.0"
    }
