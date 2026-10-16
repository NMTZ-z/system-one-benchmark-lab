"""PR #6 seventh review: every successful model result has pinned identity,
and each real Jev result is backed by at least one counted remote attempt.

No model/provider initialized, no API calls; use frozen public synthetic data.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot.__main__ import _summary, main


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "results" / "processed"


@pytest.fixture
def reports(tmp_path):
    paths = {}
    for provider in ("rule", "laya", "jev"):
        filename = f"model-backend-pilot-20261016-{provider}.json"
        copy = tmp_path / filename
        shutil.copyfile(PROCESSED / filename, copy)
        paths[provider] = copy
    return paths


def _compare(paths, output, capsys):
    exit_code = main([
        "compare", "--reports",
        *(str(paths[p]) for p in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return exit_code, capsys.readouterr().err


def _change(paths, provider, callback):
    path = paths[provider]
    report = json.loads(path.read_text(encoding="utf-8"))
    callback(report)
    path.write_text(json.dumps(report), encoding="utf-8")


@pytest.mark.parametrize("provider", ["laya", "jev"])
@pytest.mark.parametrize("field,value", [
    ("model_resolved", None),
    ("model_requested", None),
    ("model_resolved", ""),
    ("model_requested", " "),
    ("model_resolved", "jev-1.14.0"),
])
def test_each_successful_model_result_requires_consistent_identity(
    tmp_path, reports, capsys, provider, field, value,
):
    # Corrupt a second model result; the first retains complete identities.
    def corrupt(report):
        case = next(x for x in report["cases"] if x["id"] == "C03")
        assert case["status"] == "ok" and case["decision_source"] == "model"
        case[field] = value

    _change(reports, provider, corrupt)
    output = tmp_path / "compare.json"
    code, stderr = _compare(reports, output, capsys)
    assert code == 3 and (
        "model identity" in stderr or "invalid model_resolved" in stderr
    )
    assert not output.exists()


def test_model_identity_cannot_change_between_top_level_and_cases(
    tmp_path, reports, capsys,
):
    _change(reports, "jev", lambda r: r.update(requested_model="jev-1.14.0"))
    target = tmp_path / "invalid.json"
    code, stderr = _compare(reports, target, capsys)
    assert code == 3 and "model identity" in stderr
    assert not target.exists()


def test_all_model_results_require_identity_even_if_one_is_valid(
    tmp_path, reports, capsys,
):
    def corrupt(report):
        for row in report["cases"]:
            if row["decision_source"] == "model" and row["id"] != "P01":
                row["model_requested"] = None
                row["model_resolved"] = None

    _change(reports, "jev", corrupt)
    output = tmp_path / "false-valid.json"
    code, stderr = _compare(reports, output, capsys)
    assert code == 3 and (
        "model identity" in stderr or "invalid model_resolved" in stderr
    )
    assert not output.exists()


@pytest.mark.parametrize("attempts", [1, 5])
def test_remote_attempts_cannot_undercount_successful_model_cases(
    tmp_path, reports, capsys, attempts,
):
    _change(reports, "jev", lambda report: report.update(remote_attempts=attempts))
    out = tmp_path / "result.json"
    code, stderr = _compare(reports, out, capsys)
    assert code == 3 and "remote_attempts" in stderr
    assert not out.exists()


@pytest.mark.parametrize("bad_attempts", [7, 13, 999])
def test_remote_attempts_cannot_exceed_one_per_sample(
    tmp_path, reports, capsys, bad_attempts,
):
    _change(reports, "jev", lambda report: report.update(remote_attempts=bad_attempts))
    out = tmp_path / "result.json"
    code, stderr = _compare(reports, out, capsys)
    assert code == 3 and "remote_attempts" in stderr
    assert not out.exists()


@pytest.mark.parametrize("bad_unknown", [-1, 7, "0", None])
def test_unknown_usage_count_bounded_by_remote_attempts(
    tmp_path, reports, capsys, bad_unknown,
):
    _change(reports, "jev", lambda report: report.update(remote_usage_unknown_attempts=bad_unknown))
    out = tmp_path / "result.json"
    code, stderr = _compare(reports, out, capsys)
    assert code == 3 and "remote_usage_unknown_attempts" in stderr
    assert not out.exists()


def test_missing_usage_without_unknown_accounting_is_rejected(
    tmp_path, reports, capsys,
):
    def corrupt(report):
        case = next(x for x in report["cases"] if x["id"] == "C03")
        case["usage"] = None

    _change(reports, "jev", corrupt)
    out = tmp_path / "result.json"
    code, stderr = _compare(reports, out, capsys)
    assert code == 3 and "missing usage" in stderr
    assert not out.exists()


def test_forged_local_remote_attempts_rejected(tmp_path, reports, capsys):
    _change(reports, "laya", lambda report: report.update(remote_attempts=1))
    out = tmp_path / "result.json"
    code, stderr = _compare(reports, out, capsys)
    assert code == 3 and "cannot claim remote attempts" in stderr
    assert not out.exists()


def test_jev_success_must_have_actual_remote_backend(tmp_path, reports, capsys):
    def corrupt(report):
        row = next(x for x in report["cases"] if x["id"] == "P03")
        row["execution_backend"] = "mlx"

    _change(reports, "jev", corrupt)
    out = tmp_path / "result.json"
    code, stderr = _compare(reports, out, capsys)
    assert code == 3 and "remote_http backend" in stderr
    assert not out.exists()


@pytest.mark.parametrize("bad_usage", [
    {"input_tokens": "321", "output_tokens": 31},
    {"input_tokens": 321, "output_tokens": -1},
    {"input_tokens": 321},
    {"input_tokens": 321, "output_tokens": True},
])
def test_remote_usage_requires_valid_token_counts(tmp_path, reports, capsys, bad_usage):
    def corrupt(report):
        case = next(x for x in report["cases"] if x["id"] == "P01")
        case["usage"] = bad_usage

    _change(reports, "jev", corrupt)
    output = tmp_path / "invalid-usage.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3 and "invalid token usage" in error
    assert not output.exists()


def test_declared_model_version_drift_on_rule_handled_case_is_rejected(
    tmp_path, reports, capsys,
):
    def corrupt(report):
        # A case skipped by the provider cannot assert a different model.
        row = next(x for x in report["cases"] if x["id"] == "C01")
        assert row["decision_source"] == "rule"
        row["model_resolved"] = "jev-1.14.0"

    _change(reports, "jev", corrupt)
    output = tmp_path / "drift.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3 and "model identity" in error
    assert not output.exists()


def test_remote_alias_cannot_be_reported_as_pinned_model(tmp_path, reports, capsys):
    _change(reports, "jev", lambda report: report.update(requested_model="jev-latest"))
    output = tmp_path / "alias.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3 and "pinned concrete model" in error
    assert not output.exists()


def test_frozen_comparison_remains_byte_identical(tmp_path, reports, capsys):
    output = tmp_path / "new.json"
    code, stderr = _compare(reports, output, capsys)
    assert code == 0 and stderr == ""
    assert output.read_bytes() == (
        PROCESSED / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
