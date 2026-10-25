"""Independently check pre-model Git freeze and published synthetic observations."""
import copy
import json
from pathlib import Path

import pytest

from benchmarks.decision_value.evaluate import evaluate_rows
from benchmarks.decision_value.holdout_v1 import replay as frozen
from benchmarks.decision_value.holdout_v1.replay import HoldoutError, discordance

FREEZE_COMMIT = "1245a3cb17120f0f6bee198a34aa159ea3eeb851"
ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks/decision_value/holdout_v1/new_frozen_holdout_v1.jsonl"
OBS = ROOT / "benchmarks/decision_value/holdout_v1/observations_v1.jsonl"
REPORT = ROOT / "results/processed/phase8_3_new_holdout_v1.json"


def test_preregistered_commit_contains_exact_original_case_and_runner_bytes():
    entry = frozen.check_freeze(FREEZE_COMMIT)
    assert entry["case_count"] == 80
    assert entry["model_revision"] == frozen.MODEL_REVISION
    assert entry["labels_origin"] == "human-authored-synthetic-before-inference"
    assert entry["paid_provider_requests"] == 0
    assert entry["hashes"][CASES.relative_to(ROOT).as_posix()] == frozen.digest_file(CASES)


def test_original_gold_mutation_cannot_be_called_a_frozen_study(monkeypatch):
    # Simulate reading altered dataset bytes without mutating the immutable
    # source file in the working tree or changing the prereg commit.
    original_read = Path.read_bytes

    def tampered_bytes(self):
        data = original_read(self)
        if self == CASES:
            return data + b"\\n"
        return data

    monkeypatch.setattr(Path, "read_bytes", tampered_bytes)
    with pytest.raises(HoldoutError, match="frozen source has changed"):
        frozen.check_freeze(FREEZE_COMMIT)


def test_published_results_are_faithful_to_frozen_80_case_labels():
    original = frozen.read_cases()
    rows = [json.loads(x) for x in OBS.read_text().splitlines() if x.strip()]
    report = json.loads(REPORT.read_text())
    assert len(rows) == len(original) == 80
    assert len({r["case_id"] for r in rows}) == 80
    assert report["freeze_git_commit"] == FREEZE_COMMIT
    assert report["dataset_sha256"] == frozen.digest_file(CASES)
    assert report["paid_provider_requests"] == 0
    assert report["native_real_stepfun_validation"] == "NOT_RUN"
    assert report["independent_real_agent_outcome"] == "NOT_MEASURED"
    assert report["oracle_external_independence"] == "NOT_ESTABLISHED"
    original_by_id = {x["id"]: x for x in original}
    for row in rows:
        control = original_by_id[row["case_id"]]
        assert row["gold"] == {k:control["gold"][k] for k in ("acceptable", "preferred", "oracle")}
        assert row["standardized_input_sha256"] == frozen.digest(
            {k:v for k,v in control["input"].items() if k != "request_id"})
        assert row["source"] == control["source"]
        assert row["native"]["decision"] is None
        assert row["native"]["task_success"] is None
        assert row["opportunity"]["authority"]["mode"] == "shadow"
        assert row["opportunity"]["authority"]["action_allowed"] is False
    fresh = evaluate_rows(rows)
    for key,group in fresh["groups"].items():
        assert group == report["groups"][key]
        group_rows=[r for r in rows if (
            r["gate"],r["source"],r["split"]) == (
            group["gate"],group["source"],group["split"])]
        assert discordance(group_rows) == report["discordance"][key]
    assert sum(g["model_attempted"] for g in fresh["groups"].values()) == 29
    assert sum(g["model_completed"] for g in fresh["groups"].values()) == 29
    assert sum(g["native_verified_task_outcomes"] for g in fresh["groups"].values()) == 0


def test_frozen_completion_respects_original_safety_threshold_and_charged_work():
    rows=[json.loads(x) for x in OBS.read_text().splitlines() if x.strip()]
    completion=[r for r in rows if r["gate"]=="completion"]
    invoked=[r for r in completion if r["rules_model"]["model_invoked"]]
    assert len(invoked)==15
    assert all(r["rules_model"]["backend"]=="mlx" for r in invoked)
    assert sum(r["rules_model"]["safety_override"] for r in invoked) == 14
    assert not any(r["rules_model"]["guarded_decision"]=="complete" for r in completion)
    assert all(r["rules_model"]["model_completed"] for r in invoked)


def test_frozen_retry_gains_are_paired_not_cherry_picked():
    rows=[json.loads(x) for x in OBS.read_text().splitlines() if x.strip()]
    retry=[r for r in rows if r["gate"]=="retry_escalation"]
    stats=discordance(retry)
    assert stats == {
        "n":40, "both_correct":36, "rule_only_correct":0,
        "model_only_correct":4, "neither_correct":0,
        "additional_correct_choices":4,
    }
    assert sum(r["rules_model"]["model_invoked"] for r in retry)==14
    assert all(not r["rules_model"]["safety_override"] for r in retry)
