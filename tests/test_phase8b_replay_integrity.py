"""Regression guards for frozen Phase 8B replay provenance (no model inference)."""

from __future__ import annotations

import hashlib
import json
import sys

import pytest

from benchmarks.completion import phase8b_reliability
from benchmarks.completion.phase8b_audit import run
from benchmarks.completion.phase8b_offline import compare
from benchmarks.completion.phase8b_publish_summary import public_summary

STRESS_DIGEST = "fa7324fcee611988c9ed3f92d6a0ac1f7af81b9b22c2fcb219f86dbc22856b2b"


def _gold_and_trace(tmp_path):
    gold = tmp_path / "gold.jsonl"
    corpus = [
        {
            "id": "gold-continue",
            "source": "synthetic_pilot",
            "label": "continue",
            "task": "Deliver verified artifact.",
            "current_result": "Artifact missing.",
            "execution_state": {"required_step_missing": True},
        },
        {
            "id": "gold-verify",
            "source": "synthetic_pilot",
            "label": "verify",
            "task": "Confirm remote state.",
            "current_result": "Locally changed, not verified remotely.",
            "execution_state": {"verification_required": True, "final_state_verified": False},
        },
    ]
    gold.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in corpus),
        encoding="utf-8",
    )
    # Both cases resolve through deterministic rules; no HTTP/model call is made.
    audit = run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps(audit), encoding="utf-8")
    return gold, trace, corpus, audit


def test_audit_hashes_full_corpus_even_for_partial_replay(tmp_path):
    gold, _, _, report = _gold_and_trace(tmp_path)
    expected_sha256 = hashlib.sha256(gold.read_bytes()).hexdigest()
    assert report["gold_sha256"] == expected_sha256

    limited = run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 1)
    assert limited["case_count"] == 1
    assert limited["gold_sha256"] == expected_sha256


def test_identical_frozen_corpus_replays_and_propagates_digest(tmp_path):
    gold, trace, _, audit = _gold_and_trace(tmp_path)
    result = compare(trace, gold)
    assert result["gold_sha256"] == audit["gold_sha256"]
    assert result["trace_sha256"] == hashlib.sha256(trace.read_bytes()).hexdigest()
    assert result["matched_case_count"] == 2
    assert result["policies"]["8a"]["accuracy"] == 1.0


@pytest.mark.parametrize("mutation", ("execution_state", "current_result", "whitespace"))
def test_offline_replay_rejects_modified_full_corpus_with_matching_ids_labels(
    tmp_path, mutation
):
    gold, trace, corpus, _ = _gold_and_trace(tmp_path)
    if mutation == "execution_state":
        corpus[0]["execution_state"] = {"required_step_missing": False}
    elif mutation == "current_result":
        corpus[0]["current_result"] = "Changed text with the same case ID and label."
    if mutation == "whitespace":
        gold.write_bytes(gold.read_bytes() + b" ")
    else:
        gold.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in corpus),
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="corpus SHA-256 mismatch"):
        compare(trace, gold)


def test_offline_replay_requires_digest_in_trace(tmp_path):
    gold, trace, _, audit = _gold_and_trace(tmp_path)
    audit.pop("gold_sha256")
    trace.write_text(json.dumps(audit), encoding="utf-8")
    with pytest.raises(ValueError, match="missing digest"):
        compare(trace, gold)


def _valid_publication_data(tmp_path):
    frozen = {"calibration": {"sha256": "a" * 64}, "blind": {"sha256": "b" * 64}}
    (tmp_path / "phase8b-pilot-freeze.json").write_text(json.dumps(frozen))
    sha = {"cal": frozen["calibration"]["sha256"], "blind": frozen["blind"]["sha256"],
           "stress": STRESS_DIGEST}
    policy = {
        "accuracy": 1.0,
        "macro_f1": 1.0,
        "per_class": {},
        "confusion_matrix": {},
        "premature_completion_count": 0,
        "non_complete_support": 1,
        "premature_completion_wilson_95": [0.0, 0.1],
    }
    for stage, digest in sha.items():
        (tmp_path / f"phase8b-{stage}-policies.json").write_text(
            json.dumps({
                "gold_sha256": digest,
                "trace_sha256": {"cal": "c" * 64, "blind": "d" * 64, "stress": "e" * 64}[stage],
                "matched_case_count": 1,
                "policies": {name: policy for name in ("8a", "rules", "raw", "candidate")},
            })
        )
    for stage in ("cal", "blind"):
        (tmp_path / f"phase8b-{stage}-reliability.json").write_text(
            json.dumps({
                "gold_sha256": sha[stage],
                "trace_sha256": {"cal": "c" * 64, "blind": "d" * 64}[stage],
                "model_only_n": 1,
            })
        )
    return sha


def test_public_summary_rejects_replay_digest_different_from_freeze(tmp_path):
    _valid_publication_data(tmp_path)
    assert public_summary(tmp_path)["freeze_sha256"]["blind"] == "b" * 64
    changed = json.loads((tmp_path / "phase8b-blind-policies.json").read_text())
    changed["gold_sha256"] = "f" * 64
    (tmp_path / "phase8b-blind-policies.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="blind replay corpus digest"):
        public_summary(tmp_path)


def test_public_summary_accepts_matching_reliability_corpus_digest(tmp_path):
    sha = _valid_publication_data(tmp_path)
    published = public_summary(tmp_path)
    for stage in ("cal", "blind"):
        assert published["sets"][stage]["model_only_reliability"]["gold_sha256"] == sha[stage]


@pytest.mark.parametrize("stage", ("cal", "blind"))
def test_public_summary_rejects_reliability_copied_from_another_set(tmp_path, stage):
    sha = _valid_publication_data(tmp_path)
    other = "blind" if stage == "cal" else "cal"
    (tmp_path / f"phase8b-{stage}-reliability.json").write_text(
        json.dumps({
            "gold_sha256": sha[other],
            "trace_sha256": {"cal": "c" * 64, "blind": "d" * 64}[other],
            "model_only_n": 25,
        })
    )
    with pytest.raises(ValueError, match=rf"{stage} reliability corpus digest"):
        public_summary(tmp_path)


@pytest.mark.parametrize("invalid", (None, "f" * 64))
def test_public_summary_rejects_missing_or_stale_reliability_digest(tmp_path, invalid):
    _valid_publication_data(tmp_path)
    reliability = {"model_only_n": 25}
    if invalid is not None:
        reliability["gold_sha256"] = invalid
    (tmp_path / "phase8b-blind-reliability.json").write_text(json.dumps(reliability))
    with pytest.raises(ValueError, match="blind reliability corpus digest"):
        public_summary(tmp_path)


@pytest.mark.parametrize("stage", ("cal", "blind"))
def test_public_summary_rejects_reliability_from_another_trace_of_same_corpus(tmp_path, stage):
    sha = _valid_publication_data(tmp_path)
    # The corpus digest still matches; only the underlying inference trace differs.
    (tmp_path / f"phase8b-{stage}-reliability.json").write_text(json.dumps({
        "gold_sha256": sha[stage],
        "trace_sha256": "f" * 64,
        "model_only_n": 25,
    }))
    with pytest.raises(ValueError, match=rf"{stage} reliability trace digest"):
        public_summary(tmp_path)


def test_public_summary_requires_trace_digest_in_policy_and_reliability(tmp_path):
    _valid_publication_data(tmp_path)
    policy_path = tmp_path / "phase8b-cal-policies.json"
    policy = json.loads(policy_path.read_text())
    policy.pop("trace_sha256")
    policy_path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match="cal reliability trace digest"):
        public_summary(tmp_path)

    policy["trace_sha256"] = "c" * 64
    policy_path.write_text(json.dumps(policy))
    reliability_path = tmp_path / "phase8b-cal-reliability.json"
    reliability = json.loads(reliability_path.read_text())
    reliability.pop("trace_sha256")
    reliability_path.write_text(json.dumps(reliability))
    with pytest.raises(ValueError, match="cal reliability trace digest"):
        public_summary(tmp_path)


def _reliability_trace(tmp_path, digest):
    trace = tmp_path / "phase8b-cal-trace.json"
    trace.write_text(json.dumps({
        "gold_sha256": digest,
        "rows": [{
            "label": "complete",
            "raw_model_decision": "complete",
            "raw_probabilities": {"complete": .8, "continue": .1, "verify": .1},
        }],
    }))
    return trace


def test_reliability_cli_propagates_trace_corpus_sha256(tmp_path, monkeypatch, capsys):
    trace = _reliability_trace(tmp_path, "a" * 64)
    output = tmp_path / "reliability.json"
    monkeypatch.setattr(
        sys, "argv", ["phase8b_reliability.py", "--trace", str(trace), "--out", str(output)]
    )
    phase8b_reliability.main()
    capsys.readouterr()
    summary = json.loads(output.read_text())
    assert summary["gold_sha256"] == "a" * 64
    assert summary["trace_sha256"] == hashlib.sha256(trace.read_bytes()).hexdigest()
    assert summary["model_only_n"] == 1


@pytest.mark.parametrize("invalid", (None, "not-a-digest"))
def test_reliability_cli_rejects_trace_missing_or_invalid_corpus_digest(
    tmp_path, monkeypatch, invalid
):
    trace = _reliability_trace(tmp_path, invalid)
    output = tmp_path / "unverified-reliability.json"
    monkeypatch.setattr(
        sys, "argv", ["phase8b_reliability.py", "--trace", str(trace), "--out", str(output)]
    )
    with pytest.raises(ValueError, match="missing valid gold_sha256"):
        phase8b_reliability.main()
    assert not output.exists()
