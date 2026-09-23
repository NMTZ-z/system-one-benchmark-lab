"""Metrics for the LocalLLaMA/typed-decisions benchmark."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import pairwise
from typing import Any

import numpy as np


def _normalise(values: list[float]) -> np.ndarray:
    p = np.asarray(values, dtype=float)
    if not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("probabilities must be finite and non-negative")
    total = float(p.sum())
    if total <= 0:
        raise ValueError("probabilities must have positive mass")
    return p / total


def probability_keys(question: dict[str, Any]) -> list[str]:
    qtype = question["type"]
    if qtype == "choice":
        criteria = question["criteria"]
        if isinstance(criteria, dict):
            return list(criteria)
        return [str(item) for item in criteria]
    if qtype == "score":
        return [str(i) for i in range(len(question["criteria"]))]
    if qtype == "noul":
        return ["false", "true"]
    raise ValueError(f"unsupported question type: {qtype}")


def answer_distribution(
    answer: dict[str, Any], question: dict[str, Any]
) -> tuple[list[str], np.ndarray]:
    keys = probability_keys(question)
    qtype = question["type"]
    if qtype == "noul":
        p_true = float(answer["noul"])
        return keys, _normalise([1.0 - p_true, p_true])
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict):
        raise TypeError(f"{qtype} answer is missing probabilities")
    return keys, _normalise([float(probabilities.get(key, 0.0)) for key in keys])


def gold_distribution(
    gold: dict[str, Any], question: dict[str, Any]
) -> tuple[list[str], np.ndarray]:
    keys = probability_keys(question)
    probabilities = gold.get("probabilities", {})
    if question["type"] == "noul" and "true" not in probabilities:
        p_true = float(gold.get("noul", 0.5))
        return keys, _normalise([1.0 - p_true, p_true])
    return keys, _normalise([float(probabilities.get(key, 0.0)) for key in keys])


def predicted_label(
    answer: dict[str, Any], question: dict[str, Any], p: np.ndarray, keys: list[str]
) -> str:
    qtype = question["type"]
    if qtype == "choice" and answer.get("choice") in keys:
        return str(answer["choice"])
    if qtype == "noul":
        return "true" if float(answer["noul"]) >= 0.5 else "false"
    return keys[int(np.argmax(p))]


def ece_score(
    confidences: list[float], correctness: list[float], bins: int = 15
) -> float:
    conf = np.asarray(confidences, dtype=float)
    corr = np.asarray(correctness, dtype=float)
    if not len(conf):
        return float("nan")
    value = 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index, (lo, hi) in enumerate(pairwise(edges)):
        selected = (conf >= lo if index == 0 else conf > lo) & (conf <= hi)
        if selected.any():
            value += float(selected.mean()) * abs(
                float(conf[selected].mean() - corr[selected].mean())
            )
    return float(value)


def macro_f1(gold_indices: list[int], predicted_indices: list[int]) -> float:
    g = np.asarray(gold_indices)
    p = np.asarray(predicted_indices)
    values = []
    for cls in sorted(set(g.tolist()) | set(p.tolist())):
        tp = int(((p == cls) & (g == cls)).sum())
        fp = int(((p == cls) & (g != cls)).sum())
        fn = int(((p != cls) & (g == cls)).sum())
        values.append(2 * tp / max(1, 2 * tp + fp + fn))
    return float(np.mean(values)) if values else float("nan")


def score_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Score normalized decision records.

    Each record needs workflow, question_type, question, gold, and either answer
    or an error/status field. Failed decisions are reported in coverage and are
    excluded from supported-only distribution metrics.
    """

    scored: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter()

    for record in records:
        answer = record.get("answer")
        if not isinstance(answer, dict):
            failure_counts[str(record.get("status") or "error")] += 1
            continue
        try:
            keys, pred = answer_distribution(answer, record["question"])
            gold_keys, target = gold_distribution(record["gold"], record["question"])
            if keys != gold_keys:
                raise ValueError("prediction/gold key order mismatch")
            gold_label = str(record["gold"]["label"])
            pred_label = predicted_label(answer, record["question"], pred, keys)
            gold_index = keys.index(gold_label)
            pred_index = keys.index(pred_label)
            confidence = float(np.max(pred))
            correct = float(pred_label == gold_label)
            kl = float(
                sum(
                    target[i]
                    * math.log(
                        max(float(target[i]), 1e-12) / max(float(pred[i]), 1e-12)
                    )
                    for i in range(len(keys))
                    if target[i] > 0
                )
            )
            item = {
                **record,
                "_pred": pred,
                "_target": target,
                "_gold_index": gold_index,
                "_pred_index": pred_index,
                "_confidence": confidence,
                "_correct": correct,
                "_soft_accuracy": float(np.dot(pred, target)),
                "_kl": kl,
                "_tv": float(0.5 * np.abs(pred - target).sum()),
                "_brier_soft": float(np.square(pred - target).sum()),
            }
            if record["question_type"] == "score":
                predicted_score = answer.get("score")
                if predicted_score is None:
                    predicted_score = float(np.dot(np.arange(len(pred)), pred))
                item["_score_error"] = abs(
                    float(predicted_score) - float(record["gold"]["score"])
                )
            scored.append(item)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            # Malformed model outputs count against coverage instead of aborting the run.
            failure_counts[f"invalid_answer:{type(error).__name__}"] += 1

    def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return {"n": 0}
        corr = [item["_correct"] for item in items]
        conf = [item["_confidence"] for item in items]
        gold_idx = [item["_gold_index"] for item in items]
        pred_idx = [item["_pred_index"] for item in items]
        score_errors = [
            item["_score_error"] for item in items if "_score_error" in item
        ]
        return {
            "n": len(items),
            "accuracy": float(np.mean(corr)),
            "soft_accuracy": float(np.mean([item["_soft_accuracy"] for item in items])),
            "macro_f1_index": macro_f1(gold_idx, pred_idx),
            "kl_from_gold": float(np.mean([item["_kl"] for item in items])),
            "total_variation": float(np.mean([item["_tv"] for item in items])),
            "brier_vs_soft": float(np.mean([item["_brier_soft"] for item in items])),
            "ece_15": ece_score(conf, corr, bins=15),
            "mean_confidence": float(np.mean(conf)),
            "score_mae": float(np.mean(score_errors)) if score_errors else None,
            "within_1_level": (
                float(np.mean([error <= 1.0 for error in score_errors]))
                if score_errors
                else None
            ),
        }

    total = len(records)
    output = summarize(scored)
    output.update(
        total_decisions=total,
        scored_decisions=len(scored),
        coverage=(len(scored) / total if total else 0.0),
        failures=dict(sorted(failure_counts.items())),
    )

    by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scored:
        by_workflow[item["workflow"]].append(item)
        by_type[item["question_type"]].append(item)
    output["by_workflow"] = {
        key: summarize(value) for key, value in sorted(by_workflow.items())
    }
    output["by_question_type"] = {
        key: summarize(value) for key, value in sorted(by_type.items())
    }
    return output
