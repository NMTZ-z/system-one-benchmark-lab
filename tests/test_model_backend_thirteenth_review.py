"""PR #6 thirteenth Codex review: JEV usage-based cost evidence consistency.

No network, TypeSafe credentials, or model inference. Only frozen public
synthetic report fixtures; modified copies live under pytest temporary paths.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot
from local_system_one.model_backends.jev import PRICE_USD_PER_INPUT_TOKEN


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "results/processed"


@pytest.fixture
def reports(tmp_path):
    out = {}
    for provider in ("rule", "laya", "jev"):
        source = PROCESSED / f"model-backend-pilot-20261016-{provider}.json"
        target = tmp_path / f"{provider}.json"
        shutil.copyfile(source, target)
        out[provider] = target
    return out


def _change_jev(reports, change):
    path = reports["jev"]
    record = json.loads(path.read_text(encoding="utf-8"))
    change(record)
    record["summary"] = pilot._summary(record["cases"])
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def _compare(reports, output, capsys):
    code = pilot.main([
        "compare", "--reports",
        *(str(reports[p]) for p in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err


def test_frozen_jev_cost_matches_provider_price_and_known_input_tokens(reports):
    report = json.loads(reports["jev"].read_text(encoding="utf-8"))
    known_tokens = sum(
        row["usage"]["input_tokens"]
        for row in report["cases"] if row["usage"] is not None
    )
    assert known_tokens == 2397
    assert report["remote_usage_based_cost_estimate_usd"] == pytest.approx(
        known_tokens * PRICE_USD_PER_INPUT_TOKEN,
    )


@pytest.mark.parametrize("bad_usd", [0.0, 1e-9, 0.00005, 0.00009])
def test_zero_or_understated_jev_cost_rejected_even_if_summary_recomputed(
    tmp_path, reports, capsys, bad_usd,
):
    _change_jev(
        reports,
        lambda report: report.update(remote_usage_based_cost_estimate_usd=bad_usd),
    )
    out = tmp_path / "forged-cost.json"
    code, error = _compare(reports, out, capsys)
    assert code == 3 and "cost estimate below known input-token charges" in error
    assert "Traceback" not in error
    assert not out.exists()


def test_exact_known_usage_lower_bound_allowed(tmp_path, reports, capsys):
    def use_lower_bound(report):
        tokens = sum(
            row["usage"]["input_tokens"]
            for row in report["cases"] if row["usage"] is not None
        )
        report["remote_usage_based_cost_estimate_usd"] = (
            tokens * PRICE_USD_PER_INPUT_TOKEN
        )

    _change_jev(reports, use_lower_bound)
    out = tmp_path / "exact-cost.json"
    code, error = _compare(reports, out, capsys)
    assert code == 0 and error == ""
    assert out.exists()


def test_extra_charge_from_failed_response_not_erased(tmp_path, reports, capsys):
    def with_failed_response(report):
        case = next(row for row in report["cases"] if row["id"] == "C04")
        case.update(
            status="provider_error",
            decision_source="rule",
            decision="continue",
            error_type="ModelContractError",
            decision_source_note="model_failure_fail_open_continue",
            raw_model_decision="verify",
            raw_model_evidence={
                "primitive": "choice",
                "probabilities": {
                    "complete": 0.05, "verify": 0.90, "continue": 0.05,
                },
            },
            usage=None,
            correct=False,
        )
        # The real provider may have recorded billable usage before answer
        # validation failed even if that usage cannot be attached to the case.
        report["remote_usage_unknown_attempts"] = 1
        report["remote_usage_based_cost_estimate_usd"] += 0.00002

    _change_jev(reports, with_failed_response)
    out = tmp_path / "includes-failed-cost.json"
    code, error = _compare(reports, out, capsys)
    assert code == 0 and error == ""
    assert json.loads(out.read_text())["results"]["jev"]["valid"] == 11


def test_invalid_token_usage_on_failed_response_is_rejected(
    tmp_path, reports, capsys,
):
    def corrupt(report):
        case = next(row for row in report["cases"] if row["id"] == "C04")
        case["usage"] = {"input_tokens": -1, "output_tokens": 38}

    _change_jev(reports, corrupt)
    out = tmp_path / "bad-usage.json"
    code, error = _compare(reports, out, capsys)
    assert code == 3 and "invalid token usage" in error
    assert not out.exists()


def test_frozen_three_provider_comparison_is_unchanged(tmp_path, reports, capsys):
    out = tmp_path / "unchanged.json"
    code, error = _compare(reports, out, capsys)
    assert code == 0 and error == ""
    assert out.read_bytes() == (
        PROCESSED / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
