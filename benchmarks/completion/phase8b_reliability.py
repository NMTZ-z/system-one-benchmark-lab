#!/usr/bin/env python3
"""Reliability analysis of original Laya choice probabilities, offline only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

LABELS = ("complete", "continue", "verify")


def report(rows: list[dict], *, gold_sha256: str) -> dict:
    if not isinstance(gold_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", gold_sha256) is None:
        raise ValueError("reliability trace missing valid gold_sha256")
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
        "gold_sha256": gold_sha256,
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
    trace_bytes = a.trace.read_bytes()
    trace = json.loads(trace_bytes.decode("utf-8"))
    summary = report(trace["rows"], gold_sha256=trace.get("gold_sha256"))
    summary["trace_sha256"] = hashlib.sha256(trace_bytes).hexdigest()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
