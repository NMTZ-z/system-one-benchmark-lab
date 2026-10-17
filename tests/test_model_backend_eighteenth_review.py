"""PR #6 final focused fix: account for failed validated Jev votes without usage.

All observations are synthetic edits to frozen public report copies.
No Keychain, model initialization, provider calls or billable requests.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/processed"


@pytest.fixture
def reports(tmp_path):
    copies = {}
    for provider in ("rule", "laya", "jev"):
        file = tmp_path / f"{provider}.json"
        shutil.copyfile(
            RESULTS / f"model-backend-pilot-20261016-{provider}.json", file,
        )
        copies[provider] = file
    return copies


def _update(reports, modify):
    path = reports["jev"]
    report = json.loads(path.read_text(encoding="utf-8"))
    modify(report)
    for row in report["cases"]:
        row["correct"] = pilot._expected_correct(row)
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _compare(reports, tmp_path, capsys):
    output = tmp_path / "comparison.json"
    code = pilot.main([
        "compare", "--reports",
        *(str(reports[p]) for p in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err, output


def _failed_vote(report, *, usage):
    case = next(c for c in report["cases"] if c["id"] == "C04")
    case.update(
        status="provider_error",
        error_type="ModelContractError",
        decision="continue",
        decision_source="rule",
        decision_source_note="model_failure_fail_open_continue",
        raw_model_decision="complete",
        raw_model_evidence={
            "primitive": "choice",
            "probabilities": {
                "complete": .90, "verify": .05, "continue": .05,
            },
        },
        usage=usage,
    )
    # The test intentionally keeps the genuine remote model identity, backend,
    # frozen-case unsafe label and total remote attempts.
    assert case["model_resolved"] == "jev-1.13.0"
    assert case["execution_backend"] == "remote_http"


def test_missing_usage_on_failed_validated_vote_must_count_as_unknown(
    reports, tmp_path, capsys,
):
    def forged(report):
        _failed_vote(report, usage=None)
        report["remote_usage_unknown_attempts"] = 0

    _update(reports, forged)
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3
    assert "JEV missing usage on successful or failed validated model votes" in error
    assert not output.exists()


def test_correctly_counted_failed_validated_vote_keeps_raw_safety_event(
    reports, tmp_path, capsys,
):
    def accepted(report):
        _failed_vote(report, usage=None)
        report["remote_usage_unknown_attempts"] = 1

    _update(reports, accepted)
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 0 and error == ""
    results = json.loads(output.read_text())["results"]["jev"]
    assert results["unsafe_raw_model_suggestions"] == 1
    assert results["failures_or_unsupported"] == 1


def test_failed_vote_with_known_usage_does_not_need_unknown_attempt(
    reports, tmp_path, capsys,
):
    def accepted(report):
        case = next(c for c in report["cases"] if c["id"] == "C04")
        known = case["usage"]
        assert known and known["input_tokens"] > 0
        _failed_vote(report, usage=known)
        report["remote_usage_unknown_attempts"] = 0

    _update(reports, accepted)
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 0 and error == ""


def test_cannot_undercount_remote_attempts_with_failed_validated_vote(
    reports, tmp_path, capsys,
):
    def forged(report):
        _failed_vote(report, usage=None)
        report["remote_usage_unknown_attempts"] = 1
        report["remote_attempts"] -= 1

    _update(reports, forged)
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3
    assert "remote_attempts undercount failed validated model votes" in error
    assert not output.exists()


def test_unknown_usage_cannot_double_count_attempts_with_known_usage(
    reports, tmp_path, capsys,
):
    _update(reports, lambda report: report.update(remote_usage_unknown_attempts=1))
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 3
    assert "known and unknown usage counts exceed remote attempts" in error
    assert not output.exists()


@pytest.mark.parametrize("case_id", ["C04", "P01"])
def test_original_real_frozen_evidence_does_not_require_unknown_usage(
    reports, tmp_path, capsys, case_id,
):
    # Control: the published 2026-10-16 Jev run has reliable usage for all
    # six actual model calls, including the ordinary safe C04 response.
    report = json.loads(reports["jev"].read_text())
    assert next(c for c in report["cases"] if c["id"] == case_id)["usage"]
    assert report["remote_usage_unknown_attempts"] == 0
    code, error, output = _compare(reports, tmp_path, capsys)
    assert code == 0 and error == ""
    assert output.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
