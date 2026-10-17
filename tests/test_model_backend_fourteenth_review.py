"""PR #6 fourteenth review: verify all successful rule decisions by offline Gate replay.

No provider is loaded, no TypeSafe API or Keychain access. The only reference
data is the published, SHA-256-pinned 12-item synthetic corpus.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/processed"


@pytest.fixture
def reports(tmp_path):
    copied = {}
    for provider in ("rule", "laya", "jev"):
        file = tmp_path / f"{provider}.json"
        shutil.copyfile(
            RESULTS / f"model-backend-pilot-20261016-{provider}.json", file
        )
        copied[provider] = file
    return copied


def _mutate(paths, provider, case_id, **changes):
    file = paths[provider]
    report = json.loads(file.read_text(encoding="utf-8"))
    case = next(row for row in report["cases"] if row["id"] == case_id)
    case.update(changes)
    case["correct"] = pilot._expected_correct(case)
    report["summary"] = pilot._summary(report["cases"])
    file.write_text(json.dumps(report), encoding="utf-8")


def _compare(paths, output, capsys):
    code = pilot.main([
        "compare", "--reports",
        *(str(paths[provider]) for provider in ("rule", "laya", "jev")),
        "--output", str(output),
    ])
    return code, capsys.readouterr().err


def test_offline_rule_gate_replay_matches_real_frozen_rule_report(reports):
    baseline = json.loads(reports["rule"].read_text(encoding="utf-8"))
    expected = pilot._frozen_rule_gate_outcomes(pilot.FROZEN_PUBLIC_DATASET_SHA256)
    assert len(expected) == 9
    assert set(expected) == {"C01", "C02", "C03", "C04",
                             "R01", "R02", "R03", "R04", "R05"}
    for case in baseline["cases"]:
        if case["status"] == "ok" and case["decision_source"] == "rule":
            assert expected[case["id"]] == {
                "family": case["family"],
                "decision": case["decision"],
                "reason": case["decision_source_note"],
            }


@pytest.mark.parametrize("provider,case_id,replacement", [
    ("rule", "C01", "verify"),
    ("laya", "C01", "verify"),
    ("jev", "C01", "verify"),
    ("rule", "C02", "continue"),
    ("laya", "C02", "complete"),
    ("rule", "C03", "verify"),
    ("rule", "C04", "verify"),
    ("rule", "R01", "abort"),
    ("laya", "R01", "ask_user"),
    ("jev", "R01", "abort"),
    ("rule", "R02", "abort"),
    ("rule", "R03", "ask_user"),
    ("rule", "R04", "ask_user"),
    ("rule", "R05", "abort"),
    ("laya", "R05", "abort"),
])
def test_rule_case_cannot_claim_wrong_but_legal_label(
    tmp_path, reports, capsys, provider, case_id, replacement,
):
    _mutate(reports, provider, case_id, decision=replacement)
    output = tmp_path / "false-rule.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3
    assert "rule-gate decision/reason contradicts frozen Gate replay" in err
    assert not output.exists()


@pytest.mark.parametrize("provider,case_id,wrong_reason", [
    ("rule", "C01", "final_state_not_verified"),
    ("jev", "C01", "explicit_test_failure"),
    ("laya", "C02", "required_checks_incomplete"),
    ("rule", "C03", "model_unavailable_rule_only"),
    ("rule", "R01", "approval_required"),
    ("rule", "R02", "single_safe_rule_candidate"),
    ("laya", "R05", "approval_required"),
])
def test_correct_rule_decision_with_forged_reason_is_rejected(
    tmp_path, reports, capsys, provider, case_id, wrong_reason,
):
    _mutate(reports, provider, case_id, decision_source_note=wrong_reason)
    output = tmp_path / "bad-reason.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3
    assert "rule-gate decision/reason contradicts frozen Gate replay" in err
    assert not output.exists()


def test_forged_label_and_plausible_alternate_reason_still_rejected(
    tmp_path, reports, capsys,
):
    _mutate(
        reports, "rule", "C01",
        decision="verify", decision_source_note="final_state_not_verified",
    )
    output = tmp_path / "plausible-but-false.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3
    assert "rule-gate decision/reason contradicts frozen Gate replay" in err
    assert not output.exists()


def test_three_reports_coordinated_rule_tampering_is_detected(
    tmp_path, reports, capsys,
):
    for provider in reports:
        _mutate(
            reports, provider, "R02",
            decision="abort",
            decision_source_note="permanent_failure_no_alternative",
        )
    output = tmp_path / "coordinated-fraud.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3
    assert "rule-gate decision/reason contradicts frozen Gate replay" in err
    assert not output.exists()


def test_rule_case_id_must_belong_to_frozen_gate_dataset(
    tmp_path, reports, capsys,
):
    for provider in reports:
        file = reports[provider]
        report = json.loads(file.read_text())
        next(row for row in report["cases"] if row["id"] == "C01")["id"] = "C99"
        file.write_text(json.dumps(report))
    output = tmp_path / "unknown-rule.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3
    assert "rule-gate case not in frozen dataset" in err
    assert not output.exists()


def test_nonfrozen_data_cannot_supply_rule_gate_expectations(
    tmp_path, reports, capsys,
):
    for provider in reports:
        file = reports[provider]
        record = json.loads(file.read_text())
        record["dataset_sha256"] = "a" * 64
        file.write_text(json.dumps(record))
    output = tmp_path / "untrusted.json"
    code, err = _compare(reports, output, capsys)
    assert code == 3
    assert "cannot verify" in err and "non-frozen dataset" in err
    assert not output.exists()


def test_genuine_unmodified_pilot_reports_still_compare_byte_identically(
    tmp_path, reports, capsys,
):
    output = tmp_path / "comparison.json"
    code, err = _compare(reports, output, capsys)
    assert code == 0 and err == ""
    assert output.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
