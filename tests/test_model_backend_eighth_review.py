"""PR #6 eighth Codex review: bounded public-only Jev and honest rule/model evidence.

All fixtures are public synthetic data. No real Jev request, Keychain read or
model inference occurs. Genuine 2026-10-16 evidence remains read-only.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot
from benchmarks.model_backend_pilot.integrity import Provenance


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"
RESULTS = ROOT / "results/processed"


def _jev_command(dataset: Path, output: Path) -> list[str]:
    return [
        "run", "--provider", "jev", "--dataset", str(dataset),
        "--output", str(output), "--allow-remote", "--public-data-confirmed",
        "--model", "jev-1.13.0", "--max-requests", "12",
        "--max-input-bytes", "4096", "--max-usd", "0.01", "--timeout", "6",
    ]


def _compared_reports(tmp_path: Path) -> dict[str, Path]:
    result = {}
    for provider in ("rule", "laya", "jev"):
        path = tmp_path / f"{provider}.json"
        shutil.copyfile(RESULTS / f"model-backend-pilot-20261016-{provider}.json", path)
        result[provider] = path
    return result


def _compare(reports: dict[str, Path], output: Path) -> int:
    return pilot.main([
        "compare", "--reports", *(str(reports[k]) for k in ("rule", "laya", "jev")),
        "--output", str(output),
    ])


def _corrupt(reports, provider, action):
    path = reports[provider]
    report = json.loads(path.read_text(encoding="utf-8"))
    action(report)
    # Recompute the entire summary, so stale aggregates cannot be responsible
    # for detecting forged model participation.
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def test_pinned_digest_matches_published_frozen_public_dataset():
    assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == (
        pilot.FROZEN_PUBLIC_DATASET_SHA256
    )
    assert pilot.FROZEN_PUBLIC_DATASET_SHA256 == (
        "215c35e52e0c1abbe1c3219f7d24828db1fe9298d43cb2e2b5baf27c9c176c90"
    )


@pytest.mark.parametrize("mutation", ["modified_state", "changed_gold", "reordered", "whitespace"])
def test_jev_rejects_nonfrozen_but_structurally_valid_jsonl_before_provider(
    tmp_path, monkeypatch, capsys, mutation,
):
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    if mutation == "whitespace":
        lines[0] = lines[0] + " "
    elif mutation == "reordered":
        lines[0], lines[1] = lines[1], lines[0]
    else:
        first = json.loads(lines[0])
        if mutation == "modified_state":
            first["payload"]["state"]["tests_failed"] = 1
        else:
            first["gold"] = "complete"
        lines[0] = json.dumps(first, ensure_ascii=False)
    source = tmp_path / "altered-public.jsonl"
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")

    init_provider = Mock(side_effect=AssertionError("should never initialize provider"))
    provenance = Mock(side_effect=AssertionError("hash must be checked first"))
    monkeypatch.setattr(pilot, "_load_provider", init_provider)
    monkeypatch.setattr(pilot, "preflight_provenance", provenance)
    output = tmp_path / "remote-output.json"

    assert pilot.main(_jev_command(source, output)) == 3
    error = capsys.readouterr().err
    assert "frozen public synthetic" in error and "SHA-256 mismatch" in error
    assert not output.exists()
    init_provider.assert_not_called()
    provenance.assert_not_called()


def test_jev_accepts_exact_frozen_corpus_at_another_path_before_provider(
    tmp_path, monkeypatch,
):
    copied = tmp_path / "frozen-copy.jsonl"
    shutil.copyfile(DATASET, copied)
    expected = Provenance(git_sha="a" * 40, clean_at_start=True)
    monkeypatch.setattr(pilot, "preflight_provenance", lambda _root: expected)
    initialized = Mock(side_effect=AssertionError("reached isolated mock provider"))
    monkeypatch.setattr(pilot, "_load_provider", initialized)
    with pytest.raises(AssertionError, match="reached isolated mock provider"):
        pilot.main(_jev_command(copied, tmp_path / "not-written.json"))
    initialized.assert_called_once()
    assert not (tmp_path / "not-written.json").exists()


def test_jev_refuses_unclean_checkout_even_with_exact_frozen_data(
    tmp_path, monkeypatch, capsys,
):
    checked = Mock(return_value=Provenance("a" * 40, clean_at_start=False))
    init_provider = Mock(side_effect=AssertionError("should never initialize provider"))
    monkeypatch.setattr(pilot, "preflight_provenance", checked)
    monkeypatch.setattr(pilot, "_load_provider", init_provider)
    output = tmp_path / "should-not-exist.json"
    assert pilot.main(_jev_command(DATASET, output)) == 3
    assert "clean committed Git checkout required" in capsys.readouterr().err
    checked.assert_called_once()
    init_provider.assert_not_called()
    assert not output.exists()


def test_rule_only_can_evaluate_a_modified_local_synthetic_dataset(tmp_path):
    lines = DATASET.read_text(encoding="utf-8").splitlines()
    item = json.loads(lines[0])
    item["payload"]["state"]["tests_failed"] = 1
    lines[0] = json.dumps(item, ensure_ascii=False)
    altered = tmp_path / "local-rule.jsonl"
    altered.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output = tmp_path / "rules.json"
    assert pilot.main([
        "run", "--provider", "rule", "--dataset", str(altered),
        "--output", str(output),
    ]) == 2  # Three unsupported direct primitive cases, as in baseline.
    report = json.loads(output.read_text())
    assert report["provider"] == "rule"
    assert report["dataset_sha256"] != pilot.FROZEN_PUBLIC_DATASET_SHA256


@pytest.mark.parametrize("provider", ["laya", "jev"])
@pytest.mark.parametrize("case_id", ["P01", "C03", "R04"])
def test_model_case_relabelled_rule_with_original_evidence_is_rejected(
    tmp_path, capsys, provider, case_id,
):
    reports = _compared_reports(tmp_path)
    def relabel(report):
        case = next(row for row in report["cases"] if row["id"] == case_id)
        assert case["status"] == "ok" and case["decision_source"] == "model"
        case["decision_source"] = "rule"
    _corrupt(reports, provider, relabel)
    output = tmp_path / "paired.json"
    assert _compare(reports, output) == 3
    assert "rule source contradicts model evidence" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("field,value", [
    ("model_resolved", "jev-1.13.0"),
    ("model_requested", "jev-1.13.0"),
    ("execution_backend", "remote_http"),
    ("raw_model_decision", "verify"),
    ("usage", {"input_tokens": 3, "output_tokens": 1}),
])
def test_rule_case_must_have_no_model_evidence_even_with_recomputed_summary(
    tmp_path, capsys, field, value,
):
    reports = _compared_reports(tmp_path)
    def corrupt(report):
        case = next(row for row in report["cases"] if row["id"] == "C01")
        assert case["status"] == "ok" and case["decision_source"] == "rule"
        case[field] = value
    _corrupt(reports, "jev", corrupt)
    output = tmp_path / "paired.json"
    assert _compare(reports, output) == 3
    assert "rule source contradicts model evidence" in capsys.readouterr().err
    assert not output.exists()


def test_successful_none_sourced_case_rejected(tmp_path, capsys):
    reports = _compared_reports(tmp_path)

    def remove_source(report):
        case = next(c for c in report["cases"] if c["id"] == "C03")
        case["decision_source"] = "none"

    _corrupt(reports, "laya", remove_source)
    output = tmp_path / "paired.json"
    assert _compare(reports, output) == 3
    assert "successful result needs a decision source" in capsys.readouterr().err
    assert not output.exists()


def test_frozen_three_provider_evidence_still_compares_byte_identically(tmp_path):
    reports = _compared_reports(tmp_path)
    output = tmp_path / "comparison.json"
    assert _compare(reports, output) == 0
    assert output.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
