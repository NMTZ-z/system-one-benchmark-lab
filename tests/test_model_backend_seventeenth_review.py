"""PR #6 seventeenth review: provider/status/family contract invariants.

Only copies of the frozen public synthetic reports. No model loading,
TypeSafe requests, Keychain access or production policy changes.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot
from local_system_one.model_backends.jev import PRICE_USD_PER_INPUT_TOKEN

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/processed"


@pytest.fixture
def reports(tmp_path):
    copied = {}
    for provider in ("rule", "laya", "jev"):
        source = RESULTS / f"model-backend-pilot-20261016-{provider}.json"
        target = tmp_path / f"{provider}.json"
        shutil.copyfile(source, target)
        copied[provider] = target
    return copied


def _corrupt(reports, provider, case_id, mutate):
    path = reports[provider]
    report = json.loads(path.read_text(encoding="utf-8"))
    row = next(item for item in report["cases"] if item["id"] == case_id)
    mutate(report, row)
    for item in report["cases"]:
        item["correct"] = pilot._expected_correct(item)
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")


def _compare(reports, tmp_path, capsys):
    output = tmp_path / "comparison.json"
    code = pilot.main([
        "compare", "--reports",
        *(str(reports[p]) for p in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err, output


def _forge_missing_model_response(report, case, *, status="unsupported"):
    """Delete all observable model claims as in the Codex exploit."""
    previous = case.get("usage")
    case.update(
        status=status, error_type=None, decision=None,
        decision_source="none", raw_model_decision=None,
        raw_model_evidence=None, latency_ms=None,
        model_requested=None, model_resolved=None, execution_backend=None,
        usage=None, decision_source_note=None,
    )
    if report["provider"] == "jev" and status == "unsupported":
        # Make the other Jev invariants internally self-consistent too, so
        # the new provider/status validation is the ONLY cause of rejection.
        report["remote_attempts"] -= 1
        if previous:
            report["remote_usage_based_cost_estimate_usd"] -= (
                previous["input_tokens"] * PRICE_USD_PER_INPUT_TOKEN
            )


@pytest.mark.parametrize("provider", ["laya", "jev"])
@pytest.mark.parametrize("case_id", ["P01", "P02", "P03"])
def test_model_primitive_cannot_be_relabelled_unsupported(
    reports, tmp_path, capsys, provider, case_id,
):
    _corrupt(
        reports, provider, case_id,
        lambda report, row: _forge_missing_model_response(report, row),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and f"{provider} provider cannot report unsupported status" in error
    assert "Traceback" not in error
    assert not output.exists()


@pytest.mark.parametrize("provider", ["laya", "jev"])
def test_model_provider_cannot_claim_unsupported_gate_row(
    reports, tmp_path, capsys, provider,
):
    _corrupt(
        reports, provider, "C01",
        lambda report, row: row.update(
            status="unsupported", decision=None, decision_source="none",
            decision_source_note=None, execution_backend=None,
        ),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and f"{provider} provider cannot report unsupported status" in error
    assert not output.exists()


@pytest.mark.parametrize("provider", ["laya", "jev"])
def test_model_provider_invalid_status_must_be_recorded_as_provider_error(
    reports, tmp_path, capsys, provider,
):
    _corrupt(
        reports, provider, "P01",
        lambda report, row: _forge_missing_model_response(
            report, row, status="invalid",
        ),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and f"{provider} provider cannot report invalid status" in error
    assert not output.exists()


@pytest.mark.parametrize("case_id", ["C01", "R01"])
def test_rule_only_gate_cannot_claim_unsupported(
    reports, tmp_path, capsys, case_id,
):
    _corrupt(
        reports, "rule", case_id,
        lambda report, row: row.update(
            status="unsupported", decision=None, decision_source="none",
            execution_backend=None, decision_source_note=None,
        ),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and "rule-only Gate cannot report unsupported" in error
    assert not output.exists()


def test_rule_only_primitive_cannot_fake_success(
    reports, tmp_path, capsys,
):
    _corrupt(
        reports, "rule", "P01",
        lambda report, row: row.update(
            status="ok", decision="continue", decision_source="none",
        ),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and "rule-only primitive must be unsupported" in error
    assert not output.exists()


def test_rule_only_cannot_report_provider_error(reports, tmp_path, capsys):
    _corrupt(
        reports, "rule", "C01",
        lambda report, row: row.update(
            status="provider_error", error_type="FakeProviderError",
        ),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and "rule-only report cannot claim failed model evidence" in error
    assert not output.exists()


@pytest.mark.parametrize("field,forgery", [
    ("decision", "continue"),
    ("decision_source", "rule"),
    ("raw_model_decision", "complete"),
    ("model_requested", "bogus-model"),
    ("execution_backend", "remote_http"),
    ("usage", {"input_tokens": 1, "output_tokens": 0}),
    ("error_type", "FakeError"),
    ("decision_source_note", "fake_replay"),
])
def test_unsupported_rule_only_case_must_not_carry_model_or_rule_evidence(
    reports, tmp_path, capsys, field, forgery,
):
    _corrupt(
        reports, "rule", "P01",
        lambda report, row: row.update({field: forgery}),
    )
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3 and "unsupported result cannot claim execution evidence" in error
    assert not output.exists()


def test_frozen_three_provider_baseline_still_compares_byte_identically(
    reports, tmp_path, capsys,
):
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 0 and error == ""
    assert output.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
