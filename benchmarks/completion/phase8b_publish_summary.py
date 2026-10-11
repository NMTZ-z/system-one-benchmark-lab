#!/usr/bin/env python3
"""Export strictly aggregate-only Phase 8B pilot statistics, never private inputs."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REQUIRED_SETS = ("cal", "blind", "stress")
POLICIES = ("8a", "rules", "raw", "candidate")
RELIABILITY_WARNING = "small sample; this is diagnostic, not a validated calibration mapping"


LABELS = ("complete", "continue", "verify")
# Anchored to the frozen public Phase 8B evaluation protocol, not an untrusted
# manifest supplied alongside the private result files.
FROZEN_SHA256 = {
    "cal": "b91bbbfdcdc3be1000574456682647148ce7fc46f1a864fb49c9aec84cdf4dd5",
    "blind": "9074d797a7f56f9506d28199bd5680b9edc6a3108f225d3e976ba52a3921e369",
    "stress": "fa7324fcee611988c9ed3f92d6a0ac1f7af81b9b22c2fcb219f86dbc22856b2b",
}


def _policy_number(source: dict, key: str, *, nullable: bool = False):
    value = source.get(key)
    if value is None and nullable:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"invalid policy aggregate number: {key}")
    return value


def _policy_rate(source: dict, key: str, *, nullable: bool = False):
    value = _policy_number(source, key, nullable=nullable)
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"invalid policy aggregate rate: {key}")
    return value


def _policy_count(source: dict, key: str) -> int:
    value = source.get(key)
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid policy aggregate count: {key}")
    return value


def _public_policy(source: dict) -> dict:
    """Project every nested policy metric onto typed, aggregate-only fields."""
    if not isinstance(source, dict):
        raise TypeError("invalid policy aggregate record")
    classes = source.get("per_class")
    matrix = source.get("confusion_matrix")
    if not isinstance(classes, dict) or not isinstance(matrix, dict):
        raise TypeError("invalid policy aggregate class/matrix")
    public_classes = {}
    public_matrix = {}
    for label in LABELS:
        class_metrics = classes.get(label)
        matrix_row = matrix.get(label)
        if not isinstance(class_metrics, dict) or not isinstance(matrix_row, dict):
            raise TypeError("invalid policy aggregate class/matrix row")
        public_classes[label] = {
            "precision": _policy_rate(class_metrics, "precision"),
            "recall": _policy_rate(class_metrics, "recall"),
            "f1": _policy_rate(class_metrics, "f1"),
            "support": _policy_count(class_metrics, "support"),
        }
        public_matrix[label] = {
            predicted: _policy_count(matrix_row, predicted) for predicted in LABELS
        }
    wilson = source.get("premature_completion_wilson_95")
    if not isinstance(wilson, list) or len(wilson) != 2:
        raise ValueError("invalid policy aggregate Wilson interval")
    wilson_bounds = [
        _policy_rate({"bound": value}, "bound") for value in wilson
    ]
    if wilson_bounds[0] > wilson_bounds[1]:
        raise ValueError("invalid policy aggregate Wilson interval ordering")
    premature = _policy_count(source, "premature_completion_count")
    non_complete = _policy_count(source, "non_complete_support")
    if premature > non_complete:
        raise ValueError("invalid policy aggregate premature count")
    bound = _policy_rate(
        source, "premature_completion_zero_one_sided_upper_95",
        nullable=premature != 0 or non_complete == 0,
    )
    if premature == 0 and non_complete > 0:
        expected = 1 - math.pow(.05, 1 / non_complete)
        if not math.isclose(bound, expected, rel_tol=1e-12, abs_tol=1e-15):
            raise ValueError("invalid policy aggregate exact zero-event upper bound")
    elif bound is not None:
        raise ValueError("invalid policy aggregate nonzero-event upper bound")
    return {
        "accuracy": _policy_rate(source, "accuracy"),
        "macro_f1": _policy_rate(source, "macro_f1"),
        "per_class": public_classes,
        "confusion_matrix": public_matrix,
        "premature_completion_count": premature,
        "non_complete_support": non_complete,
        "premature_completion_wilson_95": wilson_bounds,
        "premature_completion_zero_one_sided_upper_95": bound,
    }


def _reliability_number(source: dict, key: str, *, nullable: bool = False):
    value = source.get(key)
    if value is None and nullable:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"invalid reliability aggregate number: {key}")
    return value


def _reliability_count(source: dict, key: str) -> int:
    value = source.get(key)
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid reliability aggregate count: {key}")
    return value


def _public_reliability(source: dict) -> dict:
    """Allowlist numeric aggregate fields; never copy arbitrary private diagnostics."""
    bins = source.get("bins")
    if not isinstance(bins, list) or len(bins) != 5:
        raise ValueError("invalid reliability aggregate bins")
    public_bins = []
    for entry in bins:
        if not isinstance(entry, dict):
            raise TypeError("invalid reliability aggregate bin")
        interval = entry.get("interval")
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("invalid reliability aggregate bin interval")
        public_bins.append({
            "interval": [
                _reliability_number({"bound": value}, "bound") for value in interval
            ],
            "count": _reliability_count(entry, "count"),
            "mean_confidence": _reliability_number(entry, "mean_confidence", nullable=True),
            "empirical_accuracy": _reliability_number(entry, "empirical_accuracy", nullable=True),
        })
    return {
        "gold_sha256": source["gold_sha256"],
        "model_only_n": _reliability_count(source, "model_only_n"),
        "multiclass_brier_mean": _reliability_number(source, "multiclass_brier_mean"),
        "mean_nll": _reliability_number(source, "mean_nll"),
        "top_label_ece_5_bins": _reliability_number(source, "top_label_ece_5_bins"),
        "observed_top_class_accuracy": _reliability_number(
            source, "observed_top_class_accuracy"
        ),
        "bins": public_bins,
        "warning": RELIABILITY_WARNING,
        "trace_sha256": source["trace_sha256"],
    }


def public_summary(private_dir: Path) -> dict:
    freeze = json.loads((private_dir / "phase8b-pilot-freeze.json").read_text())
    for name, manifest_key in (("cal", "calibration"), ("blind", "blind")):
        manifest_set = freeze.get(manifest_key)
        if (
            not isinstance(manifest_set, dict)
            or manifest_set.get("sha256") != FROZEN_SHA256[name]
        ):
            raise ValueError(f"{name} manifest corpus digest does not match declared freeze")
    frozen_sha256 = FROZEN_SHA256
    policy_trace_sha256 = {}
    report = {
        "schema_version": 1,
        "phase": "8B",
        "status": "synthetic_pilot_only_not_real_agent_validation",
        "active_completion": "NO-GO",
        "privacy": "aggregate-only; no task, result, path, model prompts, or raw telemetry",
        "sets": {},
    }
    for name in REQUIRED_SETS:
        source = json.loads((private_dir / f"phase8b-{name}-policies.json").read_text())
        if source.get("gold_sha256") != frozen_sha256[name]:
            raise ValueError(f"{name} replay corpus digest does not match frozen manifest")
        policy_trace_sha256[name] = source.get("trace_sha256")
        policies = {}
        for key in POLICIES:
            policies[key] = _public_policy(source["policies"][key])
        report["sets"][name] = {
            "cases": _policy_count(source, "matched_case_count"),
            "classes": list(LABELS),
            "policies": policies,
            "warnings": [
                "synthetic engineered cases, not genuine Hermes/DSH Agent traces",
                "calibration and blind are disjoint families but not production-grade evidence",
                "raw has no stop authority; candidate threshold has no production effect",
            ],
        }
    report["freeze_sha256"] = {
        "calibration": frozen_sha256["cal"],
        "blind": frozen_sha256["blind"],
        "stress": frozen_sha256["stress"],
    }
    for phase in ("cal", "blind"):
        reliability = json.loads((private_dir / f"phase8b-{phase}-reliability.json").read_text())
        if reliability.get("gold_sha256") != frozen_sha256[phase]:
            raise ValueError(f"{phase} reliability corpus digest does not match frozen manifest")
        trace_sha256 = policy_trace_sha256[phase]
        if (
            not isinstance(trace_sha256, str)
            or len(trace_sha256) != 64
            or any(char not in "0123456789abcdef" for char in trace_sha256)
            or reliability.get("trace_sha256") != trace_sha256
        ):
            raise ValueError(f"{phase} reliability trace digest does not match policy replay")
        report["sets"][phase]["model_only_reliability"] = _public_reliability(reliability)
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    doc = public_summary(args.private_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"Phase 8B public summary: {sum(s['cases'] for s in doc['sets'].values())} synthetic cases")


if __name__ == "__main__":
    main()
