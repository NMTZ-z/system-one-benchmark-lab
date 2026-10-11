"""Regression guards for frozen Phase 8B replay provenance (no model inference)."""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys

import pytest

from benchmarks.completion import phase8b_audit, phase8b_reliability
from benchmarks.completion.evaluate import metrics as calculate_metrics
from benchmarks.completion.evaluate_live_backend import RemoteChoiceEngine
from benchmarks.completion.phase8b_audit import run
from benchmarks.completion.phase8b_offline import compare, wilson
from benchmarks.completion.phase8b_publish_summary import public_summary

CAL_DIGEST = "b91bbbfdcdc3be1000574456682647148ce7fc46f1a864fb49c9aec84cdf4dd5"
BLIND_DIGEST = "9074d797a7f56f9506d28199bd5680b9edc6a3108f225d3e976ba52a3921e369"
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
        return dict(_synthetic_choice("invalid_choice"), backend="ane")

    monkeypatch.setattr(RemoteChoiceEngine, "decide", backend_decide)
    gold = _model_required_gold(tmp_path)
    # First row is a valid deterministic hard rule, but failure on row two
    # must abort the ENTIRE benchmark rather than publishing partial metrics.
    with pytest.raises(RuntimeError, match=fallback_reason) as error:
        run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    assert "synthetic private error detail" not in str(error.value)


@pytest.mark.parametrize(
    "invalid_probabilities",
    (
        None,
        [],
        {},
        {"complete": 0.6, "continue": 0.4},  # missing verify
        {"complete": 0.6, "continue": 0.2, "verify": 0.2, "other": 0.0},
        {"complete": -0.1, "continue": 0.6, "verify": 0.5},
        {"complete": 1.1, "continue": 0.0, "verify": -0.1},
        {"complete": float("nan"), "continue": 0.2, "verify": 0.8},
        {"complete": 0.7, "continue": float("inf"), "verify": 0.3},
        {"complete": 0.7, "continue": "0.2", "verify": 0.1},
        {"complete": True, "continue": 0.2, "verify": 0.8},
        {"complete": 0.6, "continue": 0.2, "verify": 0.1},  # sum < 1
        {"complete": 0.8, "continue": 0.2, "verify": 0.2},  # sum > 1
    ),
)
def test_audit_aborts_on_invalid_model_probability_distribution(
    tmp_path, monkeypatch, invalid_probabilities
):
    def invalid_backend(self, request):
        return dict(_synthetic_choice(), probabilities=invalid_probabilities)

    monkeypatch.setattr(RemoteChoiceEngine, "decide", invalid_backend)
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        run(_model_required_gold(tmp_path), "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)


def test_audit_accepts_four_decimal_probability_rounding(tmp_path, monkeypatch):
    distribution = {"complete": 0.4755, "continue": 0.1228, "verify": 0.4018}
    assert abs(sum(distribution.values()) - 1.0) < 1e-3
    monkeypatch.setattr(
        RemoteChoiceEngine,
        "decide",
        lambda self, request: dict(
            _synthetic_choice(), backend="ane", probabilities=distribution
        ),
    )
    result = run(_model_required_gold(tmp_path), "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    assert result["rows"][1]["raw_probabilities"] == distribution
    assert result["rows"][1]["raw_model_decision"] == "complete"


@pytest.mark.parametrize(
    ("requested", "actual"),
    (
        ("ane", "mlx"),
        ("mlx", "ane"),
        ("ane", None),
        ("mlx", "unknown"),
    ),
)
def test_forced_backend_audit_aborts_if_actual_backend_differs(
    tmp_path, monkeypatch, requested, actual
):
    def reported_backend(self, request):
        return dict(_synthetic_choice(), backend=actual)

    monkeypatch.setattr(RemoteChoiceEngine, "decide", reported_backend)
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        run(_model_required_gold(tmp_path), "http://127.0.0.1:9/v1/choice",
            requested, 0.01, 0)


@pytest.mark.parametrize("actual", ("ane", "mlx"))
def test_auto_backend_audit_allows_valid_mixed_routing(tmp_path, monkeypatch, actual):
    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(_synthetic_choice(), backend=actual),
    )
    trace = run(_model_required_gold(tmp_path), "http://127.0.0.1:9/v1/choice",
                "auto", 0.01, 0)
    assert trace["backend_request"] == "auto"
    assert trace["rows"][1]["raw_backend"] == actual
    assert trace["model_backend_distribution"] == {actual: 1}


def test_cli_rejects_forced_backend_fallback_without_writing_trace(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(
            _synthetic_choice(), backend="mlx", route_reason="ane_failure_fallback"
        ),
    )
    gold = _model_required_gold(tmp_path)
    output = tmp_path / "must-not-write-misreported-ane.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_audit.py", "--gold", str(gold), "--backend", "ane",
            "--choice-url", "http://127.0.0.1:9/v1/choice", "--out", str(output),
        ],
    )
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        phase8b_audit.main()
    assert not output.exists()


@pytest.mark.parametrize(
    ("probabilities", "decision"),
    (
        ({"complete": .10, "continue": .80, "verify": .10}, "complete"),
        ({"complete": .45, "continue": .45, "verify": .10}, "complete"),
    ),
)
def test_audit_rejects_top_label_mismatch_or_tie(
    tmp_path, monkeypatch, probabilities, decision
):
    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(
            _synthetic_choice(decision), probabilities=probabilities, backend="ane"
        ),
    )
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        run(_model_required_gold(tmp_path), "http://127.0.0.1:9/v1/choice",
            "ane", 0.01, 0)


def test_audit_cli_rejects_valid_but_misleading_top_label(tmp_path, monkeypatch):
    from benchmarks.completion import phase8b_audit

    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(
            _synthetic_choice(), backend="ane",
            probabilities={"complete": 0.1, "continue": 0.8, "verify": 0.1},
        ),
    )
    output = tmp_path / "must-not-export-inconsistent-top-label.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_audit.py", "--gold", str(_model_required_gold(tmp_path)),
            "--backend", "ane", "--out", str(output),
        ],
    )
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        phase8b_audit.main()
    assert not output.exists()


def test_audit_cli_rejects_invalid_probability_without_writing_trace(
    tmp_path, monkeypatch
):
    from benchmarks.completion import phase8b_audit

    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(
            _synthetic_choice(),
            probabilities={"complete": 0.6, "continue": 0.2, "verify": 0.1},
        ),
    )
    gold = _model_required_gold(tmp_path)
    output = tmp_path / "must-not-write-invalid-distribution.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_audit.py", "--gold", str(gold),
            "--choice-url", "http://127.0.0.1:9/v1/choice", "--out", str(output),
        ],
    )
    with pytest.raises(RuntimeError, match="model_failure_fail_open_continue"):
        phase8b_audit.main()
    assert not output.exists()


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


def test_offline_rejects_legacy_trace_with_forced_backend_fallback(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(_synthetic_choice(), backend="ane"),
    )
    gold = _model_required_gold(tmp_path)
    prior_trace = run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    prior_trace["rows"][1]["raw_backend"] = "mlx"
    prior_trace["rows"][1]["route_reason"] = "ane_failure_fallback"
    trace = tmp_path / "old-ane-contaminated-trace.json"
    trace.write_text(json.dumps(prior_trace))
    with pytest.raises(ValueError, match="backend mismatch"):
        compare(trace, gold)


def test_hardening_offline_rejects_trace_with_changed_case_source(tmp_path):
    gold, trace_path, _, trace = _gold_and_trace(tmp_path)
    trace["rows"][0]["source"] = "incorrect-slice"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="source metadata differs"):
        compare(trace_path, gold)


def test_hardening_offline_rejects_duplicate_gold_case_ids(tmp_path):
    gold, trace_path, corpus, trace = _gold_and_trace(tmp_path)
    corpus[1]["id"] = corpus[0]["id"]
    gold.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in corpus),
        encoding="utf-8",
    )
    trace["gold_sha256"] = hashlib.sha256(gold.read_bytes()).hexdigest()
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="duplicate case IDs"):
        compare(trace_path, gold)


@pytest.mark.parametrize(
    ("probabilities", "model_decision", "error"),
    (
        ({"complete": .1, "continue": .8, "verify": .1}, "complete", "argmax"),
        ({"complete": .45, "continue": .45, "verify": .10}, "complete", "ambiguous"),
    ),
)
def test_offline_replay_rejects_inconsistent_top_label(
    tmp_path, monkeypatch, probabilities, model_decision, error
):
    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(_synthetic_choice(), backend="ane"),
    )
    gold = _model_required_gold(tmp_path)
    trace_data = run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    model_row = trace_data["rows"][1]
    model_row["raw_probabilities"] = probabilities
    model_row["raw_model_decision"] = model_decision
    trace = tmp_path / "old-inconsistent-top-label.json"
    trace.write_text(json.dumps(trace_data))
    with pytest.raises(ValueError, match=error):
        compare(trace, gold)


def test_offline_rejects_trace_with_model_output_misclassified_as_rule(tmp_path):
    gold, trace_path, _, trace = _gold_and_trace(tmp_path)
    trace["rows"][0]["raw_model_decision"] = "continue"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="model fallback"):
        compare(trace_path, gold)


def _valid_publication_data(tmp_path):
    frozen = {"calibration": {"sha256": CAL_DIGEST}, "blind": {"sha256": BLIND_DIGEST}}
    (tmp_path / "phase8b-pilot-freeze.json").write_text(json.dumps(frozen))
    sha = {"cal": frozen["calibration"]["sha256"], "blind": frozen["blind"]["sha256"],
           "stress": STRESS_DIGEST}
    policies = ("8a", "rules", "raw", "candidate")
    paired = [
        {
            "id": f"fixture-{label}-{index:02d}", "label": label,
            "source": "synthetic_pilot", **{policy: label for policy in policies},
        }
        for label in ("complete", "continue", "verify")
        for index in range(15)
    ]
    # Fixture metrics are produced by the ordinary evaluator; the contract
    # validator deliberately computes them independently from paired rows.
    policy = calculate_metrics([
        {"label": row["label"], "prediction": row["8a"]} for row in paired
    ])
    policy["premature_completion_wilson_95"] = list(wilson(0, 30))
    policy["premature_completion_zero_one_sided_upper_95"] = 1 - math.pow(0.05, 1 / 30)
    for stage, digest in sha.items():
        (tmp_path / f"phase8b-{stage}-policies.json").write_text(
            json.dumps({
                "gold_sha256": digest,
                "trace_sha256": {"cal": "c" * 64, "blind": "d" * 64, "stress": "e" * 64}[stage],
                "matched_case_count": 45,
                "policies": {name: policy for name in policies},
                "paired_predictions": paired,
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


@pytest.mark.parametrize(
    ("phase", "manifest_key", "foreign_digest"),
    (
        ("cal", "calibration", "e" * 64),
        ("blind", "blind", "f" * 64),
    ),
)
def test_public_summary_rejects_consistent_foreign_manifest_and_results(
    tmp_path, phase, manifest_key, foreign_digest
):
    _valid_publication_data(tmp_path)
    manifest_path = tmp_path / "phase8b-pilot-freeze.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[manifest_key]["sha256"] = foreign_digest
    manifest_path.write_text(json.dumps(manifest))

    # The policy/reliability results now match the forged manifest exactly,
    # but no longer match the original protocol's immutable corpus digests.
    policy_path = tmp_path / f"phase8b-{phase}-policies.json"
    policy = json.loads(policy_path.read_text())
    policy["gold_sha256"] = foreign_digest
    policy_path.write_text(json.dumps(policy))
    reliability_path = tmp_path / f"phase8b-{phase}-reliability.json"
    reliability = json.loads(reliability_path.read_text())
    reliability["gold_sha256"] = foreign_digest
    reliability_path.write_text(json.dumps(reliability))

    with pytest.raises(ValueError, match=rf"{phase} manifest corpus digest"):
        public_summary(tmp_path)


@pytest.mark.parametrize(("phase", "manifest_key"), (("cal", "calibration"), ("blind", "blind")))
def test_public_summary_requires_both_declared_manifest_digests(
    tmp_path, phase, manifest_key
):
    _valid_publication_data(tmp_path)
    manifest_path = tmp_path / "phase8b-pilot-freeze.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop(manifest_key)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=rf"{phase} manifest corpus digest"):
        public_summary(tmp_path)


def test_publisher_cli_will_not_write_summary_for_foreign_manifest(tmp_path, monkeypatch):
    from benchmarks.completion import phase8b_publish_summary

    _valid_publication_data(tmp_path)
    manifest_path = tmp_path / "phase8b-pilot-freeze.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["calibration"]["sha256"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest))
    output = tmp_path / "must-not-write-forged-freeze.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_publish_summary.py", "--private-dir", str(tmp_path),
            "--out", str(output),
        ],
    )
    with pytest.raises(ValueError, match="cal manifest corpus digest"):
        phase8b_publish_summary.main()
    assert not output.exists()


def test_public_summary_rejects_replay_digest_different_from_freeze(tmp_path):
    _valid_publication_data(tmp_path)
    assert public_summary(tmp_path)["freeze_sha256"]["blind"] == BLIND_DIGEST
    changed = json.loads((tmp_path / "phase8b-blind-policies.json").read_text())
    changed["gold_sha256"] = "f" * 64
    (tmp_path / "phase8b-blind-policies.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="blind replay corpus digest"):
        public_summary(tmp_path)


@pytest.mark.parametrize("stage", ("cal", "blind", "stress"))
def test_public_policy_allowlist_drops_private_nested_fields(tmp_path, stage):
    _valid_publication_data(tmp_path)
    source_path = tmp_path / f"phase8b-{stage}-policies.json"
    source = json.loads(source_path.read_text())
    private_marker = "PRIVATE-RAW-TASK-OUTPUT-LOCAL-PATH"
    policy = source["policies"]["raw"]
    policy["private_rows"] = [{"task": private_marker}]
    source["paired_predictions"][0]["raw_task"] = private_marker
    source["paired_predictions"][0]["tool_output"] = {"raw": private_marker}
    policy["per_class"]["complete"]["raw_task"] = private_marker
    policy["per_class"]["verify"]["diagnostics"] = {"tool_output": private_marker}
    policy["per_class"]["injected_label"] = {"task": private_marker}
    policy["confusion_matrix"]["complete"]["local_path"] = private_marker
    policy["confusion_matrix"]["verify"]["raw_rows"] = [private_marker]
    policy["confusion_matrix"]["injected_label"] = {"task": private_marker}
    source["private_debug_rows"] = [{"task": private_marker}]
    source_path.write_text(json.dumps(source))

    published = public_summary(tmp_path)
    aggregate = published["sets"][stage]["policies"]["raw"]
    assert set(aggregate) == {
        "accuracy", "macro_f1", "per_class", "confusion_matrix",
        "premature_completion_count", "non_complete_support",
        "premature_completion_wilson_95",
        "premature_completion_zero_one_sided_upper_95",
    }
    expected_labels = {"complete", "continue", "verify"}
    assert set(aggregate["per_class"]) == expected_labels
    assert set(aggregate["confusion_matrix"]) == expected_labels
    for label in expected_labels:
        assert set(aggregate["per_class"][label]) == {
            "precision", "recall", "f1", "support",
        }
        assert set(aggregate["confusion_matrix"][label]) == expected_labels
    assert private_marker not in json.dumps(published)
    assert "private_rows" not in json.dumps(published)
    assert math.isclose(
        aggregate["premature_completion_zero_one_sided_upper_95"],
        1 - math.pow(0.05, 1 / 30),
    )


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("per_class.complete.precision", "PRIVATE USER PROMPT"),
        ("per_class.complete.support", True),
        ("per_class.continue.f1", {"raw_text": "PRIVATE USER PROMPT"}),
        ("confusion_matrix.complete.verify", "PRIVATE TOOL OUTPUT"),
        ("confusion_matrix.verify.complete", -1),
        ("premature_completion_wilson_95", [0, "PRIVATE VALUE"]),
        ("premature_completion_wilson_95", [0, 0.1, "PRIVATE VALUE"]),
        ("premature_completion_zero_one_sided_upper_95", "PRIVATE VALUE"),
        ("premature_completion_zero_one_sided_upper_95", None),
        ("premature_completion_zero_one_sided_upper_95", 0.1),
        ("macro_f1", float("nan")),
        ("accuracy", -0.01),
        ("accuracy", 1.01),
        ("macro_f1", -0.01),
        ("macro_f1", 1.01),
        ("per_class.complete.precision", -0.01),
        ("per_class.complete.precision", 1.01),
        ("per_class.continue.recall", -0.01),
        ("per_class.continue.recall", 1.01),
        ("per_class.verify.f1", -0.01),
        ("per_class.verify.f1", 1.01),
        ("premature_completion_wilson_95", [-0.01, 0.6]),
        ("premature_completion_wilson_95", [0.2, 1.01]),
        ("premature_completion_wilson_95", [0.8, 0.2]),
        ("premature_completion_zero_one_sided_upper_95", 1.01),
        ("non_complete_support", "PRIVATE PATH"),
        ("matched_case_count", "PRIVATE PATH"),
    ),
)
def test_public_policy_invalid_aggregate_values_fail_closed(tmp_path, field, invalid):
    _valid_publication_data(tmp_path)
    source_path = tmp_path / "phase8b-blind-policies.json"
    source = json.loads(source_path.read_text())
    if field == "matched_case_count":
        source[field] = invalid
    else:
        target = source["policies"]["candidate"]
        parts = field.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = invalid
    source_path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="invalid policy aggregate"):
        public_summary(tmp_path)


def test_public_policy_accepts_valid_rate_boundaries_and_wilson_order(tmp_path):
    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-blind-policies.json"
    source = json.loads(path.read_text())
    shifted = {"complete": "continue", "continue": "verify", "verify": "complete"}
    for row in source["paired_predictions"]:
        row["candidate"] = shifted[row["label"]]
    policy = calculate_metrics([
        {"label": row["label"], "prediction": row["candidate"]}
        for row in source["paired_predictions"]
    ])
    policy["premature_completion_wilson_95"] = list(wilson(15, 30))
    policy["premature_completion_zero_one_sided_upper_95"] = None
    source["policies"]["candidate"] = policy
    path.write_text(json.dumps(source))

    result = public_summary(tmp_path)["sets"]["blind"]["policies"]["candidate"]
    assert result["accuracy"] == 0.0
    assert result["macro_f1"] == 0.0
    assert 0 <= result["premature_completion_wilson_95"][0] <= result[
        "premature_completion_wilson_95"
    ][1] <= 1


def test_publisher_cli_refuses_out_of_range_scores_without_output(tmp_path, monkeypatch):
    from benchmarks.completion import phase8b_publish_summary

    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-stress-policies.json"
    source = json.loads(path.read_text())
    source["policies"]["raw"]["accuracy"] = 2.0
    path.write_text(json.dumps(source))
    output = tmp_path / "must-not-publish-impossible-accuracy.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_publish_summary.py", "--private-dir", str(tmp_path),
            "--out", str(output),
        ],
    )
    with pytest.raises(ValueError, match="invalid policy aggregate rate"):
        phase8b_publish_summary.main()
    assert not output.exists()


def test_public_policy_publishes_null_when_zero_event_bound_not_defined(tmp_path):
    _valid_publication_data(tmp_path)
    source_path = tmp_path / "phase8b-stress-policies.json"
    source = json.loads(source_path.read_text())
    candidate = next(
        row for row in source["paired_predictions"] if row["label"] == "continue"
    )
    candidate["raw"] = "complete"
    policy = calculate_metrics([
        {"label": row["label"], "prediction": row["raw"]}
        for row in source["paired_predictions"]
    ])
    policy["premature_completion_wilson_95"] = list(wilson(1, 30))
    policy["premature_completion_zero_one_sided_upper_95"] = None
    source["policies"]["raw"] = policy
    source_path.write_text(json.dumps(source))
    assert (
        public_summary(tmp_path)["sets"]["stress"]["policies"]["raw"][
            "premature_completion_zero_one_sided_upper_95"
        ] is None
    )


def test_publisher_cli_never_writes_unvalidated_policy_metrics(tmp_path, monkeypatch):
    from benchmarks.completion import phase8b_publish_summary

    _valid_publication_data(tmp_path)
    artifact_path = tmp_path / "phase8b-stress-policies.json"
    artifact = json.loads(artifact_path.read_text())
    artifact["policies"]["8a"]["confusion_matrix"]["complete"]["verify"] = (
        "PRIVATE USER TEXT"
    )
    artifact_path.write_text(json.dumps(artifact))
    output = tmp_path / "must-not-publish-private-policy-report.json"
    monkeypatch.setattr(
        sys, "argv",
        [
            "phase8b_publish_summary.py", "--private-dir", str(tmp_path),
            "--out", str(output),
        ],
    )
    with pytest.raises(ValueError, match="invalid policy aggregate"):
        phase8b_publish_summary.main()
    assert not output.exists()


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
        ("multiclass_brier_mean", -0.1),
        ("mean_nll", -1.0),
        ("top_label_ece_5_bins", float("nan")),
        ("top_label_ece_5_bins", -0.001),
        ("top_label_ece_5_bins", 1.001),
        ("observed_top_class_accuracy", "PRIVATE-TASK-BODY"),
        ("observed_top_class_accuracy", -0.5),
        ("observed_top_class_accuracy", 1.001),
        ("bins.0.count", True),
        ("bins.4.mean_confidence", -0.01),
        ("bins.4.mean_confidence", 1.01),
        ("bins.4.empirical_accuracy", -0.01),
        ("bins.4.empirical_accuracy", 1.01),
        ("bins.0.interval", [-0.2, 0.2]),
        ("bins.0.interval", [0.8, 0.2]),
        ("bins.4.interval", [0.8, 1.2]),
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


def test_public_reliability_accepts_valid_loss_and_rate_boundaries(tmp_path):
    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-blind-reliability.json"
    source = json.loads(path.read_text())
    source["multiclass_brier_mean"] = 0.0
    source["mean_nll"] = 0.0
    source["top_label_ece_5_bins"] = 1.0
    source["observed_top_class_accuracy"] = 0.0
    source["bins"][4]["mean_confidence"] = 1.0
    source["bins"][4]["empirical_accuracy"] = 0.0
    path.write_text(json.dumps(source))
    result = public_summary(tmp_path)["sets"]["blind"]["model_only_reliability"]
    assert result["mean_nll"] == 0
    assert result["multiclass_brier_mean"] == 0
    assert result["top_label_ece_5_bins"] == 1
    assert result["observed_top_class_accuracy"] == 0
    assert result["bins"][4]["mean_confidence"] == 1


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


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("matched_case_count", 44),
        ("matched_case_count", 46),
        ("paired_predictions", []),
        ("paired_predictions", None),
        ("policies.8a.accuracy", 0.98),
        ("policies.rules.macro_f1", 0.95),
        ("policies.candidate.per_class.complete.f1", 0.8),
        ("policies.raw.per_class.continue.support", 14),
        ("policies.raw.confusion_matrix.continue.continue", 14),
        ("policies.raw.premature_completion_count", 1),
        ("policies.raw.non_complete_support", 29),
        ("policies.raw.premature_completion_wilson_95", [0.0, 0.2]),
    ),
)
def test_hardening_rejects_inconsistent_policy_artifacts(tmp_path, field, invalid):
    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-stress-policies.json"
    source = json.loads(path.read_text())
    obj = source
    parts = field.split(".")
    for part in parts[:-1]:
        obj = obj[part]
    obj[parts[-1]] = invalid
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="(?:invalid policy aggregate|invalid phase8b data contract)"):
        public_summary(tmp_path)


@pytest.mark.parametrize("mutation", ("duplicate_id", "missing_id", "imbalanced_labels", "invalid_label"))
def test_hardening_rejects_invalid_paired_prediction_identity(tmp_path, mutation):
    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-blind-policies.json"
    source = json.loads(path.read_text())
    rows = source["paired_predictions"]
    if mutation == "duplicate_id":
        rows[1]["id"] = rows[0]["id"]
    elif mutation == "missing_id":
        rows[0]["id"] = ""
    elif mutation == "imbalanced_labels":
        rows[0]["label"] = "continue"
    else:
        rows[0]["label"] = "unreviewed"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="invalid phase8b data contract"):
        public_summary(tmp_path)


@pytest.mark.parametrize("seed", range(24))
def test_hardening_fuzzed_prediction_corruption_is_never_published(tmp_path, seed):
    # Reproducible property-style mutations without an additional dependency.
    _valid_publication_data(tmp_path)
    stage = ("cal", "blind", "stress")[seed % 3]
    path = tmp_path / f"phase8b-{stage}-policies.json"
    source = json.loads(path.read_text())
    rng = random.Random(seed)
    row = rng.choice(source["paired_predictions"])
    policy = rng.choice(("8a", "rules", "raw", "candidate"))
    new_prediction = rng.choice([label for label in ("complete", "continue", "verify")
                                 if label != row[policy]])
    row[policy] = new_prediction
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="invalid phase8b data contract"):
        public_summary(tmp_path)


@pytest.mark.parametrize(
    ("field", "invalid"),
    (
        ("model_only_n", 0),
        ("model_only_n", 2),
        ("model_only_n", 46),
        ("bins.4.count", 0),
        ("bins.4.count", 2),
        ("bins.0.mean_confidence", 0.1),
        ("bins.0.empirical_accuracy", 0.1),
        ("bins.4.mean_confidence", None),
        ("bins.4.empirical_accuracy", None),
        ("bins.4.mean_confidence", 0.5),
        ("bins.4.empirical_accuracy", 0.5),
        ("bins.4.interval", [0.7, 1.0]),
        ("top_label_ece_5_bins", 0.16),
        ("observed_top_class_accuracy", 0.8),
    ),
)
def test_hardening_rejects_self_inconsistent_reliability(tmp_path, field, invalid):
    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-cal-reliability.json"
    source = json.loads(path.read_text())
    obj = source
    parts = field.split(".")
    for key in parts[:-1]:
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    obj[parts[-1]] = invalid
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="(?:invalid reliability aggregate|invalid phase8b data contract)"):
        public_summary(tmp_path)


def test_hardening_no_report_on_cross_field_mismatch(tmp_path, monkeypatch):
    from benchmarks.completion import phase8b_publish_summary

    _valid_publication_data(tmp_path)
    path = tmp_path / "phase8b-blind-policies.json"
    data = json.loads(path.read_text())
    data["matched_case_count"] = 44
    path.write_text(json.dumps(data))
    output = tmp_path / "must-not-publish-inconsistent-statistics.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_publish_summary.py", "--private-dir", str(tmp_path),
            "--out", str(output),
        ],
    )
    with pytest.raises(ValueError, match="invalid phase8b data contract"):
        phase8b_publish_summary.main()
    assert not output.exists()


def test_hardening_rejects_legacy_raw_trace_with_invalid_probability(tmp_path, monkeypatch):
    monkeypatch.setattr(
        RemoteChoiceEngine, "decide",
        lambda self, request: dict(_synthetic_choice(), backend="ane"),
    )
    gold = _model_required_gold(tmp_path)
    trace = run(gold, "http://127.0.0.1:9/v1/choice", "ane", 0.01, 0)
    trace["rows"][1]["raw_probabilities"]["complete"] = 1.4
    path = tmp_path / "old-contaminated-probabilities.json"
    path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="model probability distribution"):
        compare(path, gold)


@pytest.mark.parametrize(
    ("probabilities", "decision", "expected_error"),
    (
        ({"complete": .1, "continue": .8, "verify": .1}, "complete", "argmax"),
        ({"complete": .45, "continue": .45, "verify": .10}, "complete", "ambiguous"),
        ({"complete": .1, "continue": .8, "verify": .1}, None, "declared top-label"),
    ),
)
def test_reliability_rejects_ambiguous_or_inconsistent_top_class(
    probabilities, decision, expected_error
):
    rows = [{
        "label": "complete", "raw_model_decision": decision,
        "raw_probabilities": probabilities,
    }]
    with pytest.raises(ValueError, match=expected_error):
        phase8b_reliability.report(rows, gold_sha256="a" * 64)


def test_reliability_correctness_is_based_on_probability_argmax():
    rows = [
        {"label": "continue", "raw_model_decision": "continue",
         "raw_probabilities": {"complete": .05, "continue": .9, "verify": .05}},
        {"label": "complete", "raw_model_decision": "verify",
         "raw_probabilities": {"complete": .05, "continue": .1, "verify": .85}},
    ]
    result = phase8b_reliability.report(rows, gold_sha256="a" * 64)
    assert result["model_only_n"] == 2
    assert result["observed_top_class_accuracy"] == .5
    assert sum(bin_["count"] for bin_ in result["bins"]) == 2


def test_reliability_cli_refuses_inconsistent_top_label_without_output(
    tmp_path, monkeypatch
):
    source = _reliability_trace(tmp_path, "a" * 64)
    doc = json.loads(source.read_text())
    doc["rows"][0]["raw_model_decision"] = "verify"
    source.write_text(json.dumps(doc))
    output = tmp_path / "must-not-export-miscalibrated-top-label.json"
    monkeypatch.setattr(
        sys, "argv", [
            "phase8b_reliability.py", "--trace", str(source), "--out", str(output),
        ],
    )
    with pytest.raises(ValueError, match="argmax"):
        phase8b_reliability.main()
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
