"""PR #6 fifth review: validate Score gold before paid inference, verify aggregates.

All tests use local public synthetic fixtures. No real provider is loaded.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"
PROCESSED = ROOT / "results/processed"


def _cases_with_score_gold(tmp_path, gold, *, criteria=None):
    rows = [json.loads(row) for row in DATA.read_text().splitlines() if row.strip()]
    score = next(row for row in rows if row["family"] == "primitive" and row["primitive"] == "score")
    score["gold"] = gold
    if criteria is not None:
        score["payload"]["criteria"] = criteria
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        "\n".join(json.dumps(row, allow_nan=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return dataset


@pytest.mark.parametrize("bad_gold", [
    "medium", "1", True, None, {}, [], -0.1, 2.1, 1e20,
])
def test_invalid_score_gold_blocks_jev_before_provider_calls(
    monkeypatch, tmp_path, capsys, bad_gold,
):
    dataset = _cases_with_score_gold(tmp_path, bad_gold)
    called = []

    def fail_if_called(args):
        called.append(args.provider)
        raise AssertionError("Never initialize or call remote provider for bad gold")

    monkeypatch.setattr(pilot, "_load_provider", fail_if_called)
    output = tmp_path / "should-not-exist.json"
    code = pilot.main([
        "run", "--provider", "jev", "--dataset", str(dataset),
        "--output", str(output), "--allow-remote",
        "--public-data-confirmed", "--max-requests", "10",
        "--max-usd", "0.01",
    ])
    assert code == 3
    assert not called
    assert not output.exists()
    assert "score gold" in capsys.readouterr().err


@pytest.mark.parametrize("bad_criteria", [[], ["one"], ["a", "b", "c", 7]])
def test_invalid_score_level_configuration_blocks_provider(
    monkeypatch, tmp_path, capsys, bad_criteria,
):
    dataset = _cases_with_score_gold(tmp_path, 1, criteria=bad_criteria)
    calls = []
    monkeypatch.setattr(pilot, "_load_provider", lambda args: calls.append(args))
    assert pilot.main([
        "run", "--provider", "jev", "--dataset", str(dataset),
        "--output", str(tmp_path / "never.json"), "--allow-remote",
        "--public-data-confirmed", "--max-requests", "1",
        "--max-usd", "0.01",
    ]) == 3
    assert calls == []
    assert "invalid score case" in capsys.readouterr().err


def _inputs(tmp_path):
    files = []
    for provider in ("rule", "laya", "jev"):
        name = f"model-backend-pilot-20261016-{provider}.json"
        path = tmp_path / name
        shutil.copyfile(PROCESSED / name, path)
        files.append(path)
    return files


def _compare_cli(paths, output):
    return pilot.main([
        "compare", "--reports", *(str(path) for path in paths),
        "--output", str(output),
    ])


@pytest.mark.parametrize("which,value", [
    ("accuracy_all_requests", 99.0),
    ("valid", "not-a-count"),
    ("model_participation_valid", 17),
    ("score_mae_valid", 0.99),
    ("unsafe_raw_model_suggestions", 100),
    ("score_valid", True),
    ("extra_metric", 10),
])
def test_stale_corrupted_summary_rejected_even_when_total_matches(
    tmp_path, capsys, which, value,
):
    inputs = _inputs(tmp_path)
    report = json.loads(inputs[2].read_text())
    assert report["summary"]["total"] == len(report["cases"])
    report["summary"][which] = value
    inputs[2].write_text(json.dumps(report), encoding="utf-8")
    output = tmp_path / "summary.json"
    assert _compare_cli(inputs, output) == 3
    error = capsys.readouterr().err
    assert "summary" in error and "case evidence" in error
    assert "Traceback" not in error
    assert not output.exists()


def test_corrupt_nested_summary_rejected_without_publishing(tmp_path, capsys):
    inputs = _inputs(tmp_path)
    report = json.loads(inputs[0].read_text())
    report["summary"]["by_family"]["retry"]["valid"] += 1
    inputs[0].write_text(json.dumps(report))
    target = tmp_path / "comparison.json"
    assert _compare_cli(inputs, target) == 3
    assert "summary.by_family.retry.valid" in capsys.readouterr().err
    assert not target.exists()


@pytest.mark.parametrize("field,bad_value", [
    ("correct", "yes"),
    ("gold", {"bad": "shape"}),
    ("unsafe", "retry_same"),
    ("latency_ms", -1),
])
def test_malformed_case_cannot_bypass_aggregate_recheck(
    tmp_path, capsys, field, bad_value,
):
    inputs = _inputs(tmp_path)
    report = json.loads(inputs[1].read_text())
    report["cases"][0][field] = bad_value
    inputs[1].write_text(json.dumps(report))
    target = tmp_path / "comparison.json"
    assert _compare_cli(inputs, target) == 3
    msg = capsys.readouterr().err
    assert ("case evidence" in msg or "case 0" in msg) and "Traceback" not in msg
    assert not target.exists()


def test_trusted_frozen_reports_still_recompute_identically(tmp_path):
    inputs = _inputs(tmp_path)
    output = tmp_path / "good.json"
    assert _compare_cli(inputs, output) == 0
    result = json.loads(output.read_text())
    assert result["results"]["jev"]["accuracy_all_requests"] == 1.0
    assert result["results"]["laya"]["valid"] == 12
    assert result["results"]["rule"]["failures_or_unsupported"] == 3
