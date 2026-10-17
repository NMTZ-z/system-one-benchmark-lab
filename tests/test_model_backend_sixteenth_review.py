"""PR #6 round 16: failed Gate Choice evidence must use exact frozen candidates.

All data is public/synthetic; no TypeSafe calls, credentials, model inference or
production changes. Reproduction changes temp copies, never frozen source.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from benchmarks.model_backend_pilot import __main__ as pilot


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/processed"
REAL_C04_OPTIONS = {"complete": 0.90, "verify": 0.05, "continue": 0.05}
REAL_R04_OPTIONS = {"retry_same": 0.04, "try_alternative": 0.92, "ask_user": 0.04}


@pytest.fixture
def reports(tmp_path):
    paths = {}
    for provider in ("rule", "laya", "jev"):
        path = tmp_path / f"{provider}.json"
        shutil.copyfile(RESULTS / f"model-backend-pilot-20261016-{provider}.json", path)
        paths[provider] = path
    return paths


def _make_failed_model_case(report, case_id, *, raw, probabilities):
    case = next(c for c in report["cases"] if c["id"] == case_id)
    # A validated TypedResult can survive a later legacy Gate error. The
    # report must retain raw safety evidence even though output is fail-open.
    case.update(
        status="provider_error", error_type="ModelContractError",
        decision_source="rule",
        raw_model_decision=raw,
        raw_model_evidence={"primitive": "choice", "probabilities": probabilities},
        correct=False,
    )
    if case_id == "C04":
        case.update(decision="continue", decision_source_note="model_failure_fail_open_continue")
    elif case_id == "R04":
        case.update(decision="try_alternative", decision_source_note="inference_failed_rule_fallback")
    else:
        raise AssertionError("unexpected synthetic test case")


def _update(reports, case_id, *, raw, probabilities, provider="jev"):
    path = reports[provider]
    report = json.loads(path.read_text(encoding="utf-8"))
    _make_failed_model_case(report, case_id, raw=raw, probabilities=probabilities)
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _compare(reports, out, capsys):
    exit_code = pilot.main([
        "compare", "--reports",
        *(str(reports[p]) for p in ("rule", "laya", "jev")),
        "--output", str(out),
    ])
    return exit_code, capsys.readouterr().err


def test_offline_capture_finds_real_gate_request_candidates(monkeypatch):
    monkeypatch.setattr(
        pilot, "_load_provider",
        lambda args: (_ for _ in ()).throw(AssertionError("no provider allowed")),
    )
    options = pilot._frozen_gate_choice_options(pilot.FROZEN_PUBLIC_DATASET_SHA256)
    assert options == {
        "C03": frozenset({"complete", "verify", "continue"}),
        "C04": frozenset({"complete", "verify", "continue"}),
        "R04": frozenset({"retry_same", "try_alternative", "ask_user"}),
    }
    # Hard-rule outcomes such as C01/R01 must never call a model.
    assert "C01" not in options
    assert "R01" not in options


def test_legitimate_failed_completion_vote_is_retained_in_safety_metrics(
    tmp_path, reports, capsys,
):
    _update(reports, "C04", raw="complete", probabilities=REAL_C04_OPTIONS)
    out = tmp_path / "verified.json"
    code, error = _compare(reports, out, capsys)
    assert code == 0 and error == ""
    results = json.loads(out.read_text(encoding="utf-8"))["results"]["jev"]
    assert results["unsafe_raw_model_suggestions"] == 1
    assert results["failures_or_unsupported"] == 1
    assert results["unsafe_final_suggestions"] == 0


@pytest.mark.parametrize("raw,probabilities", [
    ("bogus", {"bogus": .95, "other": .05}),
    ("bogus", {"bogus": .9, "other": .05, "continue": .05}),
    ("complete", {"complete": .9, "verify": .05, "other": .05}),
    ("complete", {"complete": .95, "verify": .05}),
    ("complete", {"complete": .85, "verify": .05, "continue": .05, "bogus": .05}),
    ("complete", {"complete": .9, "verify": .05, "continue ": .05}),
])
def test_failed_completion_cannot_replace_actual_choice_candidates(
    tmp_path, reports, capsys, raw, probabilities,
):
    _update(reports, "C04", raw=raw, probabilities=probabilities)
    out = tmp_path / "forged-completion.json"
    code, error = _compare(reports, out, capsys)
    assert code == 3
    assert "failed Choice candidates contradict frozen Gate request" in error
    assert not out.exists()


def test_failed_completion_with_valid_options_cannot_relabel_raw_advice(
    tmp_path, reports, capsys,
):
    _update(reports, "C04", raw="bogus", probabilities=REAL_C04_OPTIONS)
    out = tmp_path / "forged-advice.json"
    code, error = _compare(reports, out, capsys)
    assert code == 3
    assert "failed raw model decision contradicts validated vote" in error
    assert not out.exists()


def test_valid_failed_retry_model_vote_matches_actual_candidate_set(
    tmp_path, reports, capsys,
):
    _update(reports, "R04", raw="try_alternative", probabilities=REAL_R04_OPTIONS)
    out = tmp_path / "real-retry-candidates.json"
    code, error = _compare(reports, out, capsys)
    assert code == 0 and error == ""


@pytest.mark.parametrize("probabilities,raw", [
    ({"retry_same": .02, "escalate_model": .96, "ask_user": .02}, "escalate_model"),
    ({"retry_same": .04, "try_alternative": .92, "abort": .04}, "try_alternative"),
    ({"retry_same": .04, "try_alternative": .96}, "try_alternative"),
])
def test_failed_retry_model_cannot_claim_other_legal_but_unoffered_action(
    tmp_path, reports, capsys, probabilities, raw,
):
    _update(reports, "R04", raw=raw, probabilities=probabilities)
    out = tmp_path / "fake-retry.json"
    code, error = _compare(reports, out, capsys)
    assert code == 3
    assert "failed Choice candidates contradict frozen Gate request" in error
    assert not out.exists()


def test_hard_rule_case_cannot_invent_failed_model_response(
    tmp_path, reports, capsys,
):
    path = reports["jev"]
    report = json.loads(path.read_text(encoding="utf-8"))
    hard = next(c for c in report["cases"] if c["id"] == "C01")
    hard.update(
        status="provider_error", error_type="ModelContractError",
        raw_model_decision="complete",
        raw_model_evidence={
            "primitive": "choice",
            "probabilities": REAL_C04_OPTIONS,
        },
        # The hard rule never dispatched, so this is fabricated provenance.
        model_requested="jev-1.13.0", model_resolved="jev-1.13.0",
        execution_backend="remote_http",
        correct=False,
    )
    report["summary"] = pilot._summary(report["cases"])
    path.write_text(json.dumps(report), encoding="utf-8")
    out = tmp_path / "hard-rule-fraud.json"
    code, error = _compare(reports, out, capsys)
    assert code == 3
    assert "failed Choice cannot originate from frozen Gate request" in error
    assert not out.exists()


def test_unmodified_frozen_three_provider_evidence_still_compares(
    tmp_path, reports, capsys,
):
    out = tmp_path / "comparison.json"
    code, error = _compare(reports, out, capsys)
    assert code == 0 and error == ""
    assert out.read_bytes() == (
        RESULTS / "model-backend-pilot-20261016-comparison.json"
    ).read_bytes()
