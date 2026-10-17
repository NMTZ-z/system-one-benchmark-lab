"""PR #6 twelfth review: immutable Choice options for every compared case.

Uses only frozen public-synthetic reports. No model loading or remote calls.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "processed"


@pytest.fixture
def reports(tmp_path):
    items = {}
    for provider in ("rule", "laya", "jev"):
        path = tmp_path / f"{provider}.json"
        shutil.copyfile(
            RESULTS / f"model-backend-pilot-20261016-{provider}.json", path,
        )
        items[provider] = path
    return items


def _update(reports, provider, mutate):
    path = reports[provider]
    report = json.loads(path.read_text(encoding="utf-8"))
    case = next(x for x in report["cases"] if x["id"] == "P01")
    mutate(report, case)
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")


def _compare(reports, output, capsys):
    code = pilot.main([
        "compare", "--reports",
        *(str(reports[p]) for p in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err


def test_frozen_choice_options_come_from_verified_dataset():
    options = pilot._frozen_choice_options(pilot.FROZEN_PUBLIC_DATASET_SHA256)
    assert options == {"P01": frozenset({"continue", "complete"})}


@pytest.mark.parametrize("provider", ["laya", "jev"])
@pytest.mark.parametrize("bogus", ["bogus", "verify", "continue ", "retry_same"])
def test_changing_both_choice_and_raw_to_outside_option_fails(
    tmp_path, reports, capsys, provider, bogus,
):
    def change(_, case):
        case["decision"] = bogus
        case["raw_model_decision"] = bogus
        case["correct"] = pilot._expected_correct(case)

    _update(reports, provider, change)
    output = tmp_path / "paired.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3 and "Choice" in err and "outside frozen options" in err
    assert not output.exists()


@pytest.mark.parametrize("provider", ["laya", "jev"])
def test_changing_raw_only_to_unknown_label_fails(
    tmp_path, reports, capsys, provider,
):
    _update(
        reports, provider,
        lambda _, case: case.update(raw_model_decision="bogus"),
    )
    out = tmp_path / "paired.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and "Choice raw decision outside frozen options" in err
    assert not out.exists()


def test_changing_gold_to_outside_frozen_choice_options_fails(
    tmp_path, reports, capsys,
):
    def change(_, case):
        case["gold"] = "bogus"
        case["correct"] = pilot._expected_correct(case)

    _update(reports, "jev", change)
    out = tmp_path / "paired.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and "Choice gold outside frozen options" in err
    assert not out.exists()


def test_unknown_choice_case_id_cannot_borrow_other_options(
    tmp_path, reports, capsys,
):
    for path in reports.values():
        value = json.loads(path.read_text())
        value["cases"][0]["id"] = "FAKE_CHOICE_CASE"
        path.write_text(json.dumps(value))
    out = tmp_path / "paired.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and "Choice case not in frozen dataset" in err
    assert not out.exists()


def test_nonfrozen_dataset_digest_cannot_claim_choice_criteria(
    tmp_path, reports, capsys,
):
    for path in reports.values():
        value = json.loads(path.read_text())
        value["dataset_sha256"] = "a" * 64
        path.write_text(json.dumps(value))
    out = tmp_path / "paired.json"
    code, err = _compare(reports, out, capsys)
    assert code == 3 and "cannot verify Choice options for a non-frozen dataset" in err
    assert not out.exists()


def test_unmodified_frozen_comparison_remains_byte_identical(
    tmp_path, reports, capsys,
):
    out = tmp_path / "paired.json"
    code, err = _compare(reports, out, capsys)
    assert code == 0 and err == ""
    assert out.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
