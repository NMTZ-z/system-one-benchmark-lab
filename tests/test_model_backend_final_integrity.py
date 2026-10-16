"""Final integrity hardening for the research-only provider pilot.

Adversarial, deterministic fixtures. No real TypeSafe requests, models or
network access. Frozen public 2026-10-16 evidence is read-only.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot
from benchmarks.model_backend_pilot import integrity

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "benchmarks/model_backend_pilot/public_synthetic_v1.jsonl"
RESULTS = ROOT / "results/processed"


def _dataset(tmp_path, *, alter=None):
    cases = [json.loads(x) for x in DATASET.read_text(encoding="utf-8").splitlines()]
    if alter:
        alter(cases)
    path = tmp_path / "public-synthetic.jsonl"
    path.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False, allow_nan=False) for x in cases) + "\n",
        encoding="utf-8",
    )
    return path


def _pair_reports(tmp_path):
    reports = []
    for name in ("rule", "laya", "jev"):
        filename = f"model-backend-pilot-20261016-{name}.json"
        path = tmp_path / filename
        shutil.copyfile(RESULTS / filename, path)
        reports.append(path)
    return reports


def _compare(reports, out):
    return pilot.main([
        "compare", "--reports", *(str(p) for p in reports), "--output", str(out),
    ])


def _jev_run(dataset, out):
    return pilot.main([
        "run", "--provider", "jev",
        "--dataset", str(dataset), "--output", str(out),
        "--model", "jev-1.13.0", "--allow-remote",
        "--public-data-confirmed", "--max-requests", "10",
        "--max-input-bytes", "4096", "--max-usd", "0.001", "--timeout", "6",
    ])


def test_git_checkout_provenance_is_captured_at_start():
    source = integrity.preflight_provenance(ROOT)
    assert len(source.git_sha) in (40, 64)
    assert type(source.clean_at_start) is bool


def test_sanitized_public_bundle_cannot_start_billed_run(
    tmp_path, monkeypatch, capsys,
):
    # The bundle has the normal package tree but no .git. Simulating a source
    # module inside it must fail closed before ANY provider can initialize.
    export = tmp_path / "sanitized-export"
    export.mkdir()
    fake_module = export / "benchmarks/model_backend_pilot/__main__.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# public synthetic package\n")
    (export / "PUBLIC-RELEASE.json").write_text('{"source_commit":"fake"}')
    monkeypatch.setattr(pilot, "__file__", str(fake_module))
    attempts = []
    monkeypatch.setattr(pilot, "_load_provider", lambda args: attempts.append(args))
    out = tmp_path / "never-reported.json"
    assert _jev_run(DATASET, out) == 3
    assert attempts == []
    assert not out.exists()
    err = capsys.readouterr().err
    assert "Git checkout" in err and "Traceback" not in err


def test_nested_export_must_not_borrow_parent_git_provenance(
    tmp_path, monkeypatch,
):
    # A nested source export must not silently inherit another project's SHA.
    # This deliberately creates a disposable tiny Git repository in pytest tmp.
    import subprocess
    parent = tmp_path / "unrelated-project"
    parent.mkdir()
    subprocess.run(["git", "init", "-q", str(parent)], check=True, capture_output=True)
    nested = parent / "export"
    nested.mkdir()
    with pytest.raises(ValueError, match="own Git checkout root"):
        integrity.preflight_provenance(nested)


@pytest.mark.parametrize("provider", ["rule", "jev"])
def test_invalid_output_directory_fails_before_provider(
    tmp_path, monkeypatch, capsys, provider,
):
    output_dir = tmp_path / "occupied"
    output_dir.mkdir()
    calls = []
    monkeypatch.setattr(pilot, "_load_provider", lambda args: calls.append(args))
    args = [
        "run", "--provider", provider, "--dataset", str(DATASET),
        "--output", str(output_dir),
    ]
    if provider == "jev":
        args += [
            "--allow-remote", "--public-data-confirmed",
            "--max-requests", "2", "--max-usd", "0.001",
        ]
    assert pilot.main(args) == 3
    assert not calls
    assert "output must be a file" in capsys.readouterr().err


@pytest.mark.parametrize(
    "bad_case",
    [
        lambda rows: rows[0].update(gold="unsupported-option"),
        lambda rows: rows[0]["payload"].pop("state"),
        lambda rows: rows[2].update(gold="true"),
        lambda rows: rows[4].update(gold="not-a-completion-decision"),
        lambda rows: rows[4]["payload"]["execution_state"].update(tests_run=-1),
        lambda rows: rows[8].update(gold="not-a-retry-decision"),
        lambda rows: rows[8]["payload"]["history"].update(attempts=-2),
    ],
)
def test_entire_dataset_preflight_prevents_late_row_billing(
    tmp_path, monkeypatch, capsys, bad_case,
):
    source = _dataset(tmp_path, alter=bad_case)
    attempts = Mock(side_effect=AssertionError("provider must never initialize"))
    monkeypatch.setattr(pilot, "_load_provider", attempts)
    out = tmp_path / "should-not-exist.json"
    assert _jev_run(source, out) == 3
    attempts.assert_not_called()
    assert not out.exists()
    assert "dataset line" in capsys.readouterr().err


def test_duplicate_dataset_json_keys_rejected_before_provider(
    tmp_path, monkeypatch, capsys,
):
    content = DATASET.read_text(encoding="utf-8").splitlines()
    content[0] = content[0][:-1] + ', "gold": "complete"}'
    dataset = tmp_path / "duplicate.jsonl"
    dataset.write_text("\n".join(content) + "\n", encoding="utf-8")
    load_provider = Mock()
    monkeypatch.setattr(pilot, "_load_provider", load_provider)
    assert _jev_run(dataset, tmp_path / "out.json") == 3
    load_provider.assert_not_called()
    assert "duplicate JSON object key" in capsys.readouterr().err


def test_real_readonly_evidence_still_compares_and_matches_expected_sha(tmp_path):
    sources = _pair_reports(tmp_path)
    output = tmp_path / "paired.json"
    assert _compare(sources, output) == 0
    comparison = json.loads(output.read_text(encoding="utf-8"))
    assert comparison["results"]["jev"]["accuracy_all_requests"] == 1.0
    assert comparison["results"]["laya"]["accuracy_all_requests"] == pytest.approx(9 / 11)
    assert comparison["results"]["rule"]["valid"] == 9
    assert comparison["git_sha"] == (
        "935c58f19b8ccf6817b7e7561276b7141e9549e3"
    )
    assert not (RESULTS / "model-backend-pilot-20261016-jev.json").is_symlink()


@pytest.mark.parametrize("which_field,change", [
    ("decision", "verify"),
    ("gold", "verify"),
    ("status", "provider_error"),
])
def test_classification_correct_recomputed_from_evidence(
    tmp_path, capsys, which_field, change,
):
    reports = _pair_reports(tmp_path)
    jev = json.loads(reports[2].read_text())
    case = jev["cases"][0]
    assert case["id"] == "P01" and case["correct"] is True
    case[which_field] = change
    reports[2].write_text(json.dumps(jev))
    out = tmp_path / "reject.json"
    assert _compare(reports, out) == 3
    message = capsys.readouterr().err
    assert "correct contradicts" in message and "Traceback" not in message
    assert not out.exists()


def test_correct_flag_changed_alone_cannot_forge_lower_accuracy(tmp_path, capsys):
    reports = _pair_reports(tmp_path)
    jev = json.loads(reports[2].read_text())
    jev["cases"][0]["correct"] = False
    # Fake a compatible aggregate in the same report.
    jev["summary"] = pilot._summary(jev["cases"])
    reports[2].write_text(json.dumps(jev))
    assert _compare(reports, tmp_path / "reject.json") == 3
    assert "correct contradicts" in capsys.readouterr().err


@pytest.mark.parametrize("field,new_value", [
    ("gold", "verify"),
    ("unsafe", ["continue"]),
    ("requires_verification", True),
])
def test_cross_provider_frozen_case_fields_cannot_diverge(
    tmp_path, capsys, field, new_value,
):
    reports = _pair_reports(tmp_path)
    jev = json.loads(reports[2].read_text())
    row = jev["cases"][0]
    row[field] = new_value
    if field == "gold":
        row["correct"] = False
    jev["summary"] = pilot._summary(jev["cases"])
    reports[2].write_text(json.dumps(jev))
    assert _compare(reports, tmp_path / "reject.json") == 3
    assert "inconsistent frozen " + field in capsys.readouterr().err


def test_atomic_write_failure_preserves_original_and_removes_temp(
    tmp_path, monkeypatch,
):
    output = tmp_path / "existing.json"
    output.write_text("ORIGINAL-EVIDENCE\n")
    def fail_replace(*args, **kwargs):
        raise OSError("simulated disk operation failure")
    monkeypatch.setattr(integrity.os, "replace", fail_replace)
    with pytest.raises(OSError):
        integrity.write_report(output, {"result": "new"}, ensure_ascii=True)
    assert output.read_text() == "ORIGINAL-EVIDENCE\n"
    assert {p.name for p in tmp_path.iterdir()} == {"existing.json"}


def test_atomic_write_does_not_mutate_another_hardlink_inode(tmp_path):
    source = tmp_path / "important-original.json"
    source.write_text("ORIGINAL-EVIDENCE\n")
    alias = tmp_path / "output.json"
    os.link(source, alias)
    integrity.preflight_report_output(alias, inputs=[], kind="compare")
    integrity.write_report(alias, {"new": "report"}, ensure_ascii=True)
    assert source.read_text() == "ORIGINAL-EVIDENCE\n"
    assert json.loads(alias.read_text()) == {"new": "report"}
    assert not alias.samefile(source)


def test_nested_duplicate_json_key_in_comparison_rejected(tmp_path, capsys):
    reports = _pair_reports(tmp_path)
    text = reports[1].read_text()
    text = text.replace('"valid": 12,', '"valid": 12, "valid": 12,', 1)
    reports[1].write_text(text)
    assert _compare(reports, tmp_path / "reject.json") == 3
    assert "duplicate JSON object key" in capsys.readouterr().err
