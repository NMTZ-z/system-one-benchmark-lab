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
    unknown["gate"] = "completion"
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
