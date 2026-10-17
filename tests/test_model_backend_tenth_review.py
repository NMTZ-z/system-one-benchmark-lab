"""PR #6 tenth review: failed raw advice corroboration and legal Gate labels.

Every fixture is synthetic or a local copy of already-frozen public reports.
No API calls, credentials, ANE model loading or production changes.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "results/processed"


@pytest.fixture
def paired_reports(tmp_path):
    paths = {}
    for provider in ("rule", "laya", "jev"):
        dest = tmp_path / f"{provider}.json"
        shutil.copyfile(
            PROCESSED / f"model-backend-pilot-20261016-{provider}.json", dest
        )
        paths[provider] = dest
    return paths


def _update(paths, provider, callback):
    path = paths[provider]
    report = json.loads(path.read_text(encoding="utf-8"))
    callback(report)
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")


def _compare(paths, out, capsys):
    code = pilot.main([
        "compare", "--reports",
        *(str(paths[p]) for p in ("rule", "laya", "jev")),
        "--output", str(out),
    ])
    return code, capsys.readouterr().err


def _with_failed_validated_vote(report):
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
                "complete": 0.90, "verify": 0.05, "continue": 0.05,
            },
        },
        correct=False,
    )


def test_failed_real_model_advice_keeps_unsafe_raw_evidence(
    tmp_path, paired_reports, capsys,
):
    _update(paired_reports, "jev", _with_failed_validated_vote)
    output = tmp_path / "comparison.json"
    code, err = _compare(paired_reports, output, capsys)
    assert code == 0 and err == ""
    report = json.loads(output.read_text())
    assert report["results"]["jev"]["unsafe_raw_model_suggestions"] == 1
    assert report["results"]["jev"]["unsafe_final_suggestions"] == 0
    assert report["results"]["jev"]["failures_or_unsupported"] == 1


@pytest.mark.parametrize(
    "tamper",
    [
        lambda c: c.update(raw_model_decision="verify"),
        lambda c: c.update(raw_model_decision=None),
        lambda c: c.update(raw_model_evidence=None),
        lambda c: c.update(raw_model_decision=None, raw_model_evidence=None),
        lambda c: c["raw_model_evidence"].update(primitive="noul"),
        lambda c: c["raw_model_evidence"]["probabilities"].update({
            "complete": 0.05, "verify": 0.90, "continue": 0.05,
        }),
        lambda c: c["raw_model_evidence"]["probabilities"].update({
            "complete": 1.0, "verify": 0.6, "continue": 0.05,
        }),
        lambda c: c["raw_model_evidence"]["probabilities"].update(
            complete="0.90"
        ),
        lambda c: c.update(model_resolved=None),
        lambda c: c.update(execution_backend="mlx"),
    ],
)
def test_failed_raw_model_evidence_cannot_be_erased_or_forged(
    tmp_path, paired_reports, capsys, tamper,
):
    def corrupt(report):
        _with_failed_validated_vote(report)
        case = next(c for c in report["cases"] if c["id"] == "C04")
        tamper(case)

    _update(paired_reports, "jev", corrupt)
    output = tmp_path / "corrupt.json"
    code, error = _compare(paired_reports, output, capsys)
    assert code == 3
    assert (
        "failed raw model" in error
        or "raw evidence" in error
        or "failed model probability" in error
        or "failed Jev advice" in error
    )
    assert "Traceback" not in error
    assert not output.exists()


def test_rule_only_cannot_forge_failed_provider_raw_event(
    tmp_path, paired_reports, capsys,
):
    def forge(report):
        case = next(c for c in report["cases"] if c["id"] == "C04")
        case.update(
            status="provider_error", decision="continue",
            raw_model_decision="complete", correct=False,
        )

    _update(paired_reports, "rule", forge)
    output = tmp_path / "forged.json"
    code, err = _compare(paired_reports, output, capsys)
    assert code == 3 and "rule-only report cannot claim failed model evidence" in err
    assert not output.exists()


def test_unverified_failed_raw_vote_is_not_trusted(
    tmp_path, paired_reports, capsys,
):
    def forge(report):
        case = next(c for c in report["cases"] if c["id"] == "C04")
        case.update(
            status="provider_error", decision="continue", correct=False,
            raw_model_decision="complete",
        )

    _update(paired_reports, "jev", forge)
    output = tmp_path / "unknown-vote.json"
    code, err = _compare(paired_reports, output, capsys)
    assert code == 3 and "lacks validated vote evidence" in err
    assert not output.exists()


@pytest.mark.parametrize(
    "provider, case_id, invalid",
    [
        ("rule", "C01", "bogus"),
        ("rule", "C02", "abort"),
        ("jev", "C01", "retry_same"),
        ("rule", "R01", "bogus"),
        ("rule", "R02", "complete"),
        ("laya", "R01", "continue"),
        ("jev", "R03", ""),
        ("rule", "C01", 1),
        ("rule", "R01", True),
    ],
)
def test_illegal_deterministic_gate_decisions_are_rejected(
    tmp_path, paired_reports, capsys, provider, case_id, invalid,
):
    def corrupt(report):
        case = next(c for c in report["cases"] if c["id"] == case_id)
        assert case["decision_source"] == "rule"
        case["decision"] = invalid
        case["correct"] = pilot._expected_correct(case)

    _update(paired_reports, provider, corrupt)
    output = tmp_path / "invalid-label.json"
    code, err = _compare(paired_reports, output, capsys)
    assert code == 3
    assert ("invalid Completion decision label" in err or
            "invalid Retry decision label" in err)
    assert not output.exists()


@pytest.mark.parametrize(
    "provider, case_id, invalid, marker",
    [
        ("laya", "P01", False, "Choice decision type"),
        ("jev", "P03", "true", "Noul decision type"),
        ("laya", "P02", 12.0, "Score decision range"),
    ],
)
def test_primitive_decision_type_and_range_are_checked(
    tmp_path, paired_reports, capsys, provider, case_id, invalid, marker,
):
    def corrupt(report):
        case = next(c for c in report["cases"] if c["id"] == case_id)
        case["decision"] = invalid
        case["correct"] = pilot._expected_correct(case)

    _update(paired_reports, provider, corrupt)
    output = tmp_path / "invalid-primitive.json"
    code, err = _compare(paired_reports, output, capsys)
    assert code == 3 and marker in err
    assert not output.exists()


def test_unchanged_public_three_provider_results_remain_byte_identical(
    tmp_path, paired_reports, capsys,
):
    output = tmp_path / "comparison.json"
    code, err = _compare(paired_reports, output, capsys)
    assert code == 0 and err == ""
    assert output.read_bytes() == (
        PROCESSED / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
