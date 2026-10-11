"""Independent, fail-closed consistency checks for frozen Phase 8B artifacts.

These checks deliberately do not call evaluate.metrics, phase8b_offline.wilson,
or phase8b_reliability.report. Published numbers must agree with evidence,
not merely have plausible types or fall within valid numeric ranges.
Private paired rows are consumed in memory and never included in the output.
"""
from __future__ import annotations

import math
from collections import Counter

LABELS = ("complete", "continue", "verify")
POLICIES = ("8a", "rules", "raw", "candidate")
FROZEN_CASES_PER_SET = 45
FROZEN_SUPPORT_PER_CLASS = 15
FLOAT_TOLERANCE = 1e-10


def _reject(detail: str) -> None:
    raise ValueError(f"invalid phase8b data contract: {detail}")


def _equal_rate(actual: float, expected: float, detail: str) -> None:
    if not math.isclose(actual, expected, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE):
        _reject(detail)


def require_choice_distribution(probabilities: object) -> None:
    """Check the original typed-choice distribution without changing its values."""
    if (
        not isinstance(probabilities, dict)
        or set(probabilities) != set(LABELS)
        or any(
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
            for value in probabilities.values()
        )
        # The local service rounds each class to four decimal places.
        or not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-3, rel_tol=0)
    ):
        _reject("invalid model probability distribution")


def require_top_label_consistency(probabilities: object, decision: object) -> str:
    """Require an unambiguous argmax that agrees with the declared model choice.

    The service rounds probabilities before returning them. When multiple
    classes share the highest rounded probability, top-label correctness is
    ambiguous; fail closed rather than invent a tie-break for calibration.
    """
    require_choice_distribution(probabilities)
    if decision not in LABELS:
        _reject("invalid declared top-label decision")
    maximum = max(probabilities.values())
    winners = [label for label in LABELS if probabilities[label] == maximum]
    if len(winners) != 1:
        _reject("ambiguous top label in rounded probabilities")
    top_label = winners[0]
    if decision != top_label:
        _reject("declared model decision disagrees with probability argmax")
    return top_label


def _wilson_interval(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.959963984540054
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - radius), min(1.0, centre + radius))


def validate_policy_bundle(source: dict, published: dict, *, phase: str) -> None:
    """Independently reproduce every published policy count and score from paired rows."""
    rows = source.get("paired_predictions")
    if not isinstance(rows, list) or len(rows) != FROZEN_CASES_PER_SET:
        _reject(f"{phase} missing or partial frozen paired predictions")
    if published["cases"] != FROZEN_CASES_PER_SET:
        _reject(f"{phase} published case count differs from frozen 45 cases")

    observed_ids: set[str] = set()
    labels: Counter[str] = Counter()
    matrices = {
        policy: {truth: {prediction: 0 for prediction in LABELS} for truth in LABELS}
        for policy in POLICIES
    }
    for row in rows:
        if not isinstance(row, dict):
            _reject(f"{phase} invalid paired prediction row")
        identifier, label = row.get("id"), row.get("label")
        if not isinstance(identifier, str) or not identifier or identifier in observed_ids:
            _reject(f"{phase} duplicate or missing paired case identifier")
        if label not in LABELS:
            _reject(f"{phase} invalid paired case label")
        observed_ids.add(identifier)
        labels[label] += 1
        for policy in POLICIES:
            predicted = row.get(policy)
            if predicted not in LABELS:
                _reject(f"{phase} invalid {policy} prediction")
            matrices[policy][label][predicted] += 1

    if any(labels[label] != FROZEN_SUPPORT_PER_CLASS for label in LABELS):
        _reject(f"{phase} frozen class support differs from 15 per label")

    for policy, matrix in matrices.items():
        metrics = published["policies"][policy]
        if metrics["confusion_matrix"] != matrix:
            _reject(f"{phase} {policy} confusion matrix disagrees with paired rows")
        non_complete = sum(
            matrix[label][prediction]
            for label in LABELS if label != "complete"
            for prediction in LABELS
        )
        premature = sum(matrix[label]["complete"] for label in LABELS if label != "complete")
        if metrics["non_complete_support"] != non_complete:
            _reject(f"{phase} {policy} non-complete support disagrees with paired rows")
        if metrics["premature_completion_count"] != premature:
            _reject(f"{phase} {policy} premature completion count disagrees with matrix")

        diagonal = sum(matrix[label][label] for label in LABELS)
        _equal_rate(
            metrics["accuracy"], diagonal / FROZEN_CASES_PER_SET,
            f"{phase} {policy} accuracy disagrees with confusion matrix",
        )
        f1_scores = []
        for label in LABELS:
            true_positive = matrix[label][label]
            actual = sum(matrix[label].values())
            predicted = sum(matrix[truth][label] for truth in LABELS)
            precision = true_positive / predicted if predicted else 0.0
            recall = true_positive / actual if actual else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            actual_metrics = metrics["per_class"][label]
            if actual_metrics["support"] != actual:
                _reject(f"{phase} {policy} {label} support disagrees with matrix")
            for name, expected in (("precision", precision), ("recall", recall), ("f1", f1)):
                _equal_rate(
                    actual_metrics[name], expected,
                    f"{phase} {policy} {label} {name} disagrees with matrix",
                )
            f1_scores.append(f1)
        _equal_rate(
            metrics["macro_f1"], sum(f1_scores) / len(LABELS),
            f"{phase} {policy} macro F1 disagrees with matrix",
        )

        for given, correct in zip(
            metrics["premature_completion_wilson_95"],
            _wilson_interval(premature, non_complete),
        ):
            _equal_rate(given, correct, f"{phase} {policy} Wilson interval inconsistent")
        exact_bound = (
            -math.expm1(math.log(0.05) / non_complete)
            if premature == 0 and non_complete else None
        )
        value = metrics["premature_completion_zero_one_sided_upper_95"]
        if exact_bound is None:
            if value is not None:
                _reject(f"{phase} {policy} zero-event bound must be null")
        else:
            _equal_rate(value, exact_bound, f"{phase} {policy} zero-event bound inconsistent")


def validate_reliability_summary(summary: dict, *, phase: str) -> None:
    """Reconstruct binned ECE and accuracy without using the report producer."""
    n = summary["model_only_n"]
    bins = summary["bins"]
    if not isinstance(n, int) or isinstance(n, bool) or not (0 < n <= FROZEN_CASES_PER_SET):
        _reject(f"{phase} invalid model-only count")

    total, correct = 0, 0
    ece = 0.0
    for i, bin_ in enumerate(bins):
        count = bin_["count"]
        low, high = bin_["interval"]
        _equal_rate(low, i / 5, f"{phase} incorrect bin interval")
        _equal_rate(high, (i + 1) / 5, f"{phase} incorrect bin interval")
        confidence, accuracy = bin_["mean_confidence"], bin_["empirical_accuracy"]
        total += count
        if count == 0:
            if confidence is not None or accuracy is not None:
                _reject(f"{phase} empty bin must have null statistics")
            continue
        if confidence is None or accuracy is None:
            _reject(f"{phase} nonempty bin missing statistics")
        if not low - FLOAT_TOLERANCE <= confidence <= high + FLOAT_TOLERANCE:
            _reject(f"{phase} bin confidence outside its stated interval")
        inferred_correct = accuracy * count
        if not math.isclose(inferred_correct, round(inferred_correct), abs_tol=FLOAT_TOLERANCE):
            _reject(f"{phase} bin accuracy incompatible with integer correct count")
        correct += round(inferred_correct)
        ece += count * abs(confidence - accuracy) / n

    if total != n:
        _reject(f"{phase} model-only bin counts do not add to sample total")
    _equal_rate(
        summary["top_label_ece_5_bins"], ece,
        f"{phase} ECE inconsistent with confidence bins",
    )
    _equal_rate(
        summary["observed_top_class_accuracy"], correct / n,
        f"{phase} model accuracy inconsistent with confidence bins",
    )
