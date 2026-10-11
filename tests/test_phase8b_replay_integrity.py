"""Regression guards for frozen Phase 8B replay provenance (no model inference)."""

from __future__ import annotations

import hashlib
import json
import sys

import pytest

from benchmarks.completion import phase8b_audit, phase8b_reliability
from benchmarks.completion.evaluate_live_backend import RemoteChoiceEngine
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


@pytest.mark.parametrize(
    ("execution_state", "expected_reason", "expected_decision"),
    (
        ({"blocking_failure": True}, "blocking_failure", "continue"),
        ({"required_artifact_missing": True}, "required_artifact_missing", "continue"),
        ({"required_step_missing": True}, "required_step_missing", "continue"),
        ({"required_checks_completed": False}, "required_checks_incomplete", "continue"),
        ({"tests_run": 2, "tests_passed": 1}, "explicit_test_failure", "continue"),
        ({"conflicting_evidence": True}, "conflicting_evidence", "verify"),
        ({"verification_required": True}, "final_state_not_verified", "verify"),
    ),
)
def test_audit_accepts_all_existing_hard_gate_reasons(
    tmp_path, monkeypatch, execution_state, expected_reason, expected_decision
):
    def unexpectedly_called_backend(self, request):
        raise AssertionError("deterministic rules must skip model inference")

    monkeypatch.setattr(RemoteChoiceEngine, "decide", unexpectedly_called_backend)
    gold = tmp_path / "hard-only.jsonl"
    gold.write_text(json.dumps({
        "id": "hard-rule-1",
        "source": "synthetic",
        "label": expected_decision,
        "task": "Synthetic task",
        "current_result": "Synthetic result",
        "execution_state": execution_state,
    }) + "\n", encoding="utf-8")
    result = run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    assert result["case_count"] == 1
    assert result["rows"][0]["deterministic_rule"] == expected_decision
    assert result["rows"][0]["rule_reason"] == expected_reason
    assert result["raw_counts"] == {}


def _model_required_gold(tmp_path):
    gold = tmp_path / "audit-model-input.jsonl"
    cases = [
        {
            "id": "hard-rule-first",
            "source": "synthetic",
            "label": "continue",
            "task": "Finish synthetic artifact",
            "current_result": "A prerequisite is missing.",
            "execution_state": {"required_step_missing": True},
        },
        {
            "id": "model-required-second",
            "source": "synthetic",
            "label": "complete",
            "task": "Confirm a synthetic artifact",
            "current_result": "All explicit deliverables appear ready.",
            "execution_state": {},
        },
    ]
    gold.write_text(
        "".join(json.dumps(case) + "\n" for case in cases), encoding="utf-8"
    )
    return gold


def _synthetic_choice(decision="complete"):
    return {
        "decision": decision,
        "probabilities": {"complete": 0.95, "continue": 0.03, "verify": 0.02},
        "confidence": 0.95,
        "backend": "mlx",
        "route_reason": "synthetic_test",
        "token_count": 5,
        "latency_ms": 1,
    }


def test_audit_accepts_true_hard_rule_and_model_success(tmp_path, monkeypatch):
    monkeypatch.setattr(RemoteChoiceEngine, "decide", lambda self, req: _synthetic_choice())
    report = run(_model_required_gold(tmp_path), "http://127.0.0.1:9/v1/choice", "mlx", 0.01, 0)
    assert report["case_count"] == 2
    hard, model = report["rows"]
    assert hard["deterministic_rule"] == "continue"
    assert hard["rule_reason"] == "required_step_missing"
    assert hard["raw_model_decision"] is None
    assert model["deterministic_rule"] is None
    assert model["raw_model_decision"] == "complete"
    assert model["final_decision"] == "complete"
    assert report["complete_threshold_unchanged"] == 0.70
    assert report["rule_counts"] == {"required_step_missing": 1}


@pytest.mark.parametrize(
    ("failure", "fallback_reason"),
    (
        ("timeout", "model_failure_fail_open_continue"),
        ("invalid_model_value", "invalid_model_value_fail_open_continue"),
    ),
)
def test_audit_aborts_on_model_fail_open_instead_of_miscounting_as_rule(
    tmp_path, monkeypatch, failure, fallback_reason
):
    def backend_decide(self, req):
        if failure == "timeout":
            raise TimeoutError("synthetic private error detail")
        return _synthetic_choice("invalid_choice")

    monkeypatch.setattr(RemoteChoiceEngine, "decide", backend_decide)
    gold = _model_required_gold(tmp_path)
    # First row is a valid deterministic hard rule, but failure on row two
    # must abort the ENTIRE benchmark rather than publishing partial metrics.
    with pytest.raises(RuntimeError, match=fallback_reason) as error:
        run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    assert "synthetic private error detail" not in str(error.value)


def test_audit_cli_does_not_write_metrics_when_backend_is_dead(
    tmp_path, monkeypatch
):
    def dead_backend(self, req):
        raise TimeoutError("do not expose raw error text")

    monkeypatch.setattr(RemoteChoiceEngine, "decide", dead_backend)
    gold = _model_required_gold(tmp_path)
    output = tmp_path / "should-not-exist.json"
    monkeypatch.setattr(sys, "argv", [
        "phase8b_audit.py", "--gold", str(gold),
        "--choice-url", "http://127.0.0.1:9/v1/choice",
        "--out", str(output),
    ])
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        phase8b_audit.main()
    assert not output.exists()


@pytest.mark.parametrize(
    "fallback_reason",
    ("model_failure_fail_open_continue", "invalid_model_value_fail_open_continue"),
)
def test_offline_rejects_legacy_trace_with_model_fallback_rule(
    tmp_path, fallback_reason
):
    gold, trace_path, _, trace = _gold_and_trace(tmp_path)
    row = trace["rows"][0]
    row["final_reason"] = fallback_reason
    row["rule_reason"] = fallback_reason
    row["deterministic_rule"] = "continue"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="model fallback"):
        compare(trace_path, gold)


def test_offline_rejects_trace_with_model_output_misclassified_as_rule(tmp_path):
    gold, trace_path, _, trace = _gold_and_trace(tmp_path)
    trace["rows"][0]["raw_model_decision"] = "continue"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="model fallback"):
        compare(trace_path, gold)


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
                "multiclass_brier_mean": 0.1,
                "mean_nll": 0.2,
                "top_label_ece_5_bins": 0.15,
                "observed_top_class_accuracy": 1.0,
                "bins": [
                    {
                        "interval": [i / 5, (i + 1) / 5],
                        "count": int(i == 4),
                        "mean_confidence": 0.85 if i == 4 else None,
                        "empirical_accuracy": 1.0 if i == 4 else None,
                    }
                    for i in range(5)
                ],
                "warning": "small sample; this is diagnostic, not a validated calibration mapping",
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


@pytest.mark.parametrize("phase", ("cal", "blind"))
def test_public_reliability_allowlist_drops_private_fields_recursively(tmp_path, phase):
    _valid_publication_data(tmp_path)
    artifact_path = tmp_path / f"phase8b-{phase}-reliability.json"
    source = json.loads(artifact_path.read_text())
    private_marker = "PRIVATE-RAW-PROMPT-PATH-AND-TOOL-OUTPUT"
    source.update({
        "raw_rows": [{"task": private_marker, "id": "private-id"}],
        "local_paths": [f"/private/experiments/{private_marker}"],
        "unreviewed_diagnostics": {"full_text": private_marker},
        "warning": private_marker,
    })
    source["bins"][0]["raw_tool_output"] = private_marker
    source["bins"][1]["unreviewed_diagnostics"] = {"prompt": private_marker}
    artifact_path.write_text(json.dumps(source))
    published = public_summary(tmp_path)
    exported = published["sets"][phase]["model_only_reliability"]
    assert set(exported) == {
        "gold_sha256", "trace_sha256", "model_only_n",
        "multiclass_brier_mean", "mean_nll", "top_label_ece_5_bins",
        "observed_top_class_accuracy", "bins", "warning",
    }
    for histogram_bin in exported["bins"]:
        assert set(histogram_bin) == {
            "interval", "count", "mean_confidence", "empirical_accuracy"
        }
    assert exported["warning"] == (
        "small sample; this is diagnostic, not a validated calibration mapping"
    )
    assert private_marker not in json.dumps(published)
    assert "raw_rows" not in json.dumps(published)
    assert "local_paths" not in json.dumps(published)


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("model_only_n", "PRIVATE-TASK-BODY"),
        ("model_only_n", True),
        ("multiclass_brier_mean", {"task": "PRIVATE-TASK-BODY"}),
        ("top_label_ece_5_bins", float("nan")),
        ("observed_top_class_accuracy", "PRIVATE-TASK-BODY"),
        ("bins.0.count", True),
        ("bins.0.mean_confidence", "PRIVATE-TASK-BODY"),
        ("bins.0.interval", [0, "PRIVATE-TASK-BODY"]),
        ("bins.0.interval", [0.0, 0.1, "PRIVATE-TASK-BODY"]),
    ),
)
def test_public_reliability_invalid_known_fields_fail_closed(tmp_path, field, invalid):
    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-cal-reliability.json"
    source = json.loads(path.read_text())
    keys = field.split(".")
    target = source
    for key in keys[:-1]:
        target = target[int(key)] if isinstance(target, list) else target[key]
    target[keys[-1]] = invalid
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="invalid reliability aggregate"):
        public_summary(tmp_path)


def test_publisher_cli_never_writes_unvalidated_reliability_metrics(
    tmp_path, monkeypatch
):
    from benchmarks.completion import phase8b_publish_summary

    _valid_publication_data(tmp_path)
    source = tmp_path / "phase8b-blind-reliability.json"
    artifact = json.loads(source.read_text())
    artifact["model_only_n"] = "PRIVATE RAW USER TEXT"
    source.write_text(json.dumps(artifact))
    output = tmp_path / "must-not-write-public-result.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_publish_summary.py", "--private-dir", str(tmp_path),
            "--out", str(output),
        ],
    )
    with pytest.raises(ValueError, match="invalid reliability aggregate"):
        phase8b_publish_summary.main()
    assert not output.exists()


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
