"""PR #6 fifteenth review: freeze *all* case labels independently of reports.

Only copied 12-item public synthetic evidence is used. No local inference,
TypeSafe requests, model downloads, or production Gate changes are performed.
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
def reports(tmp_path):
    copied = {}
    for provider in ("rule", "laya", "jev"):
        source = PROCESSED / f"model-backend-pilot-20261016-{provider}.json"
        output = tmp_path / f"{provider}.json"
        shutil.copyfile(source, output)
        copied[provider] = output
    return copied


def _corrupt_all(reports, edit):
    """Change each input in sync and recompute its entire summary.

    This is the exact adversarial scenario missed by pairwise equality checks.
    """
    for provider, path in reports.items():
        report = json.loads(path.read_text(encoding="utf-8"))
        edit(report)
        for case in report["cases"]:
            case["correct"] = pilot._expected_correct(case)
        report["summary"] = pilot._summary(report["cases"])
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _compare(reports, output, capsys):
    code = pilot.main([
        "compare", "--reports",
        *(str(reports[name]) for name in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err


@pytest.mark.parametrize("field,new_value", [
    ("unsafe", []),
    ("unsafe", ["verify"]),
    ("unsafe", ["complete", "continue"]),
    ("gold", "complete"),
    ("requires_verification", True),
])
def test_synchronized_c04_metadata_tampering_rejected(
    tmp_path, reports, capsys, field, new_value,
):
    def forge(report):
        case = next(row for row in report["cases"] if row["id"] == "C04")
        case[field] = new_value

    _corrupt_all(reports, forge)
    output = tmp_path / "synchronized-corrupt.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3
    assert f"{field} contradicts frozen dataset" in error
    assert not output.exists()


def test_three_way_corruption_can_hide_laya_unsafe_event_without_our_check(reports):
    # Prove the dangerous modification affects published safety metrics,
    # not just formatting, so an apparent zero is never accepted as evidence.
    before = json.loads(reports["laya"].read_text())
    assert before["summary"]["unsafe_raw_model_suggestions"] == 1

    def remove_labels(report):
        next(c for c in report["cases"] if c["id"] == "C04")["unsafe"] = []

    _corrupt_all(reports, remove_labels)
    after = json.loads(reports["laya"].read_text())
    assert after["summary"]["unsafe_raw_model_suggestions"] == 0


@pytest.mark.parametrize("case_id,field,new_value", [
    ("P01", "gold", "complete"),  # Legal Choice label, but false gold.
    ("P03", "gold", False),  # Legal Noul boolean, but false gold.
    ("P02", "gold", 2),  # In-range Score level, but false gold.
    ("C01", "unsafe", []),
    ("R01", "requires_verification", False),
    ("R01", "unsafe", []),
    ("R04", "gold", "ask_user"),  # Legal Retry label, but false gold.
    ("R05", "requires_verification", True),
])
def test_synchronized_gold_safety_and_verification_forgery_rejected(
    tmp_path, reports, capsys, case_id, field, new_value,
):
    def forge(report):
        next(c for c in report["cases"] if c["id"] == case_id)[field] = new_value

    _corrupt_all(reports, forge)
    output = tmp_path / "coordinated.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3
    assert f"{field} contradicts frozen dataset" in error
    assert not output.exists()


def test_missing_same_case_in_all_three_reports_is_rejected(
    tmp_path, reports, capsys,
):
    def omit(report):
        report["cases"] = [
            c for c in report["cases"] if c["id"] != "R05"
        ]

    _corrupt_all(reports, omit)
    output = tmp_path / "shortened.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3 and "case count differs from frozen dataset" in error
    assert not output.exists()


def test_synchronized_swapped_case_ids_are_rejected(
    tmp_path, reports, capsys,
):
    def switch(report):
        for row in report["cases"]:
            if row["id"] == "C03":
                row["id"] = "C04"
            elif row["id"] == "C04":
                row["id"] = "C03"

    _corrupt_all(reports, switch)
    output = tmp_path / "swapped.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3
    assert ("ID/order contradicts frozen dataset" in error
            or "rule-gate decision/reason contradicts frozen Gate replay" in error)
    assert not output.exists()


def test_existing_one_provider_disagreement_retains_specific_diagnostic(
    tmp_path, reports, capsys,
):
    path = reports["laya"]
    report = json.loads(path.read_text())
    next(c for c in report["cases"] if c["id"] == "C04")["unsafe"] = []
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report))

    output = tmp_path / "reject.json"
    code, error = _compare(reports, output, capsys)
    assert code == 3 and "inconsistent frozen unsafe across providers" in error
    assert not output.exists()


def test_genuine_public_reports_still_compare_byte_identically(
    tmp_path, reports, capsys,
):
    output = tmp_path / "baseline.json"
    code, error = _compare(reports, output, capsys)
    assert code == 0 and error == ""
    assert output.read_bytes() == (
        PROCESSED / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
