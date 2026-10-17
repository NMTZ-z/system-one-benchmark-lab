"""PR #6 eleventh Codex review: Score bounds must match verified case rubric.

Read-only frozen public evidence; no model, Keychain or remote network access.
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
    out = {}
    for provider in ("rule", "laya", "jev"):
        filename = f"model-backend-pilot-20261016-{provider}.json"
        path = tmp_path / filename
        shutil.copyfile(RESULTS / filename, path)
        out[provider] = path
    return out


def compare(reports, output, capsys):
    code = pilot.main([
        "compare", "--reports",
        *(str(reports[k]) for k in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err


def mutate_report(reports, provider, change):
    path = reports[provider]
    data = json.loads(path.read_text(encoding="utf-8"))
    row = next(x for x in data["cases"] if x["id"] == "P02")
    change(data, row)
    data["summary"] = pilot._summary(data["cases"])
    path.write_text(json.dumps(data), encoding="utf-8")


def test_frozen_p02_score_has_three_levels():
    bounds = pilot._frozen_score_level_limits(pilot.FROZEN_PUBLIC_DATASET_SHA256)
    assert bounds == {"P02": 2}


@pytest.mark.parametrize("provider", ["laya", "jev"])
@pytest.mark.parametrize("wrong_score", [2.0001, 3.0, 9.0])
def test_score_above_case_levels_rejected_even_with_forged_raw_and_summary(
    tmp_path, reports, capsys, provider, wrong_score,
):
    def tamper(_, row):
        row["decision"] = wrong_score
        row["raw_model_decision"] = wrong_score
    mutate_report(reports, provider, tamper)

    output = tmp_path / "comparison.json"
    code, err = compare(reports, output, capsys)
    assert code == 3 and "invalid Score decision range for case levels" in err
    assert not output.exists()


@pytest.mark.parametrize("gold", [2.5, 3.0, 9.0])
def test_score_gold_outside_case_levels_is_rejected(
    tmp_path, reports, capsys, gold,
):
    mutate_report(reports, "jev", lambda _, row: row.update(gold=gold))
    output = tmp_path / "comparison.json"
    code, err = compare(reports, output, capsys)
    assert code == 3 and "Score gold outside the case's levels" in err
    assert not output.exists()


def test_score_case_id_must_exist_in_verified_frozen_corpus(
    tmp_path, reports, capsys,
):
    for provider in reports:
        path = reports[provider]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["cases"][1]["id"] = "FAKE_SCORE_ID"
        path.write_text(json.dumps(report), encoding="utf-8")
    output = tmp_path / "comparison.json"
    code, err = compare(reports, output, capsys)
    assert code == 3 and "Score case not in frozen dataset" in err
    assert not output.exists()


def test_cannot_verify_non_frozen_score_rubric(
    tmp_path, reports, capsys,
):
    for provider in reports:
        path = reports[provider]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["dataset_sha256"] = "a" * 64
        path.write_text(json.dumps(report), encoding="utf-8")
    output = tmp_path / "comparison.json"
    code, err = compare(reports, output, capsys)
    assert code == 3 and "cannot verify Score level count" in err
    assert not output.exists()


def test_frozen_comparison_remains_byte_identical(
    tmp_path, reports, capsys,
):
    output = tmp_path / "comparison.json"
    code, err = compare(reports, output, capsys)
    assert code == 0 and err == ""
    assert output.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
