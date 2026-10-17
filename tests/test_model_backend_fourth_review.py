"""PR #6 fourth review: hardlink-safe run writes and strict comparison shape.

All fixtures are local public synthetic data. No remote calls or Laya models.
"""
from __future__ import annotations

import json
import os
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot.__main__ import compare, main


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("output_alias", ("same_path", "symlink", "hardlink"))
def test_run_never_overwrites_frozen_dataset_via_alias(tmp_path, output_alias, capsys):
    original = PROJECT_ROOT / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"
    dataset = tmp_path / "frozen.jsonl"
    shutil.copyfile(original, dataset)
    expected = dataset.read_bytes()
    output = tmp_path / "out.json"
    if output_alias == "same_path":
        output = dataset
    elif output_alias == "symlink":
        output.symlink_to(dataset)
    else:
        os.link(dataset, output)
        assert output.samefile(dataset)
        assert output.resolve() != dataset.resolve()

    code = main([
        "run", "--provider", "rule", "--dataset", str(dataset),
        "--output", str(output),
    ])
    assert code == 3
    assert "output may not overwrite input dataset" in capsys.readouterr().err
    assert dataset.read_bytes() == expected
    if output_alias != "same_path":
        assert output.read_bytes() == expected


@pytest.fixture
def comparison_inputs(tmp_path):
    original = PROJECT_ROOT / "results/processed"
    inputs = []
    for provider in ("rule", "laya", "jev"):
        name = f"model-backend-pilot-20261016-{provider}.json"
        dest = tmp_path / name
        shutil.copyfile(original / name, dest)
        inputs.append(dest)
    return inputs


def test_clean_frozen_reports_still_compare(comparison_inputs, tmp_path):
    output = tmp_path / "comparison.json"
    assert compare(Namespace(reports=comparison_inputs, output=output)) == 0
    report = json.loads(output.read_text())
    assert set(report["results"]) == {"rule", "laya", "jev"}


@pytest.mark.parametrize("non_object", ("[]", "null", '"string"', "7"))
def test_comparison_rejects_nonobject_reports_with_controlled_cli_error(
    comparison_inputs, tmp_path, non_object, capsys,
):
    comparison_inputs[1].write_text(non_object)
    output = tmp_path / "comparison.json"
    argv = ["compare", "--reports", *map(str, comparison_inputs), "--output", str(output)]
    assert main(argv) == 3
    message = capsys.readouterr().err
    assert "must be a JSON object" in message
    assert "Traceback" not in message
    assert not output.exists()


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda d: d.pop("provider"), "provider"),
        (lambda d: d.pop("git_sha"), "git_sha"),
        (lambda d: d.pop("cases"), "cases"),
        (lambda d: d.update(cases=[None]), "case 0"),
        (lambda d: d["cases"][0].pop("id"), "missing id"),
        (lambda d: d["cases"][0].pop("model_resolved"), "model_resolved"),
        (lambda d: d["cases"][0].pop("status"), "invalid status"),
        (lambda d: d.update(summary=None), "invalid summary"),
        (lambda d: d["summary"].update(total=999), "total mismatch"),
        (lambda d: d.pop("remote_attempts"), "remote_attempts"),
        (lambda d: d.update(schema_version="wrong-version"), "unsupported schema_version"),
    ],
)
def test_comparison_rejects_malformed_or_missing_fields(
    comparison_inputs, tmp_path, mutate, expected, capsys,
):
    report = json.loads(comparison_inputs[2].read_text())
    mutate(report)
    comparison_inputs[2].write_text(json.dumps(report))
    output = tmp_path / "comparison.json"
    argv = ["compare", "--reports", *map(str, comparison_inputs), "--output", str(output)]
    assert main(argv) == 3
    stderr = capsys.readouterr().err
    assert expected in stderr and "Traceback" not in stderr
    assert not output.exists()


def test_nonfinite_exponent_in_comparison_report_is_controlled(
    comparison_inputs, tmp_path, capsys,
):
    original = comparison_inputs[0].read_text()
    comparison_inputs[0].write_text(original.replace('"total": 12', '"total": 1e999', 1))
    out = tmp_path / "summary.json"
    assert main([
        "compare", "--reports", *map(str, comparison_inputs),
        "--output", str(out),
    ]) == 3
    assert "finite" in capsys.readouterr().err
    assert not out.exists()
