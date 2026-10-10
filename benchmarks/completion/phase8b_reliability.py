#!/usr/bin/env python3
"""Reliability analysis of original Laya choice probabilities, offline only."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

LABELS = ("complete", "continue", "verify")


def report(rows: list[dict]) -> dict:
    selected = [r for r in rows if r["raw_probabilities"] is not None]
    if not selected:
        raise ValueError("missing model predictions")
    n = len(selected)
    brier = 0.0
    nll = 0.0
    bins = [{"count": 0, "confidence_sum": 0.0, "correct": 0} for _ in range(5)]
    for row in selected:
        probabilities = row["raw_probabilities"]
        for label in LABELS:
            brier += (probabilities[label] - float(row["label"] == label)) ** 2
        nll -= math.log(max(1e-12, probabilities[row["label"]]))
        confidence = max(probabilities.values())
        idx = min(4, int(confidence * 5))
        bins[idx]["count"] += 1
        bins[idx]["confidence_sum"] += confidence
        bins[idx]["correct"] += int(row["raw_model_decision"] == row["label"])
    ece = 0.0
    stats = []
    for i, bin_ in enumerate(bins):
        size = bin_["count"]
        if size:
            acc = bin_["correct"] / size
            mean_conf = bin_["confidence_sum"] / size
            ece += (size / n) * abs(mean_conf - acc)
        else:
            acc = mean_conf = None
        stats.append({"interval": [i / 5, (i + 1) / 5], "count": size,
                      "mean_confidence": mean_conf, "empirical_accuracy": acc})
    return {
        "model_only_n": n, "multiclass_brier_mean": brier / n,
        "mean_nll": nll / n, "top_label_ece_5_bins": ece,
        "observed_top_class_accuracy": sum(r["raw_model_decision"] == r["label"] for r in selected) / n,
        "bins": stats,
        "warning": "small sample; this is diagnostic, not a validated calibration mapping",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trace", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    rows = json.loads(a.trace.read_text())["rows"]
    summary = report(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
