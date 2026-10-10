"""Regression guards for frozen Phase 8B replay provenance (no model inference)."""

from __future__ import annotations

import hashlib
import json

import pytest

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


def test_public_summary_rejects_replay_digest_different_from_freeze(tmp_path):
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
                "matched_case_count": 1,
                "policies": {name: policy for name in ("8a", "rules", "raw", "candidate")},
            })
        )
    for stage in ("cal", "blind"):
        (tmp_path / f"phase8b-{stage}-reliability.json").write_text("{}")

    assert public_summary(tmp_path)["freeze_sha256"]["blind"] == "b" * 64
    changed = json.loads((tmp_path / "phase8b-blind-policies.json").read_text())
    changed["gold_sha256"] = "f" * 64
    (tmp_path / "phase8b-blind-policies.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="blind replay corpus digest"):
        public_summary(tmp_path)
