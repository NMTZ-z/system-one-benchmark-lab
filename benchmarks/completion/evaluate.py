#!/usr/bin/env python3
"""Evaluate Completion Gate against a labeled JSONL corpus.

Metrics are emitted separately for real and synthetic slices. The output never
copies task/result bodies; only IDs, labels, predictions and runtime metadata are
persisted.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

LABELS = ("complete", "continue", "verify")


def public_path(path: Path) -> str:
    """Return a repository-relative path without leaking a local home directory."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = {truth: {pred: 0 for pred in LABELS} for truth in LABELS}
    for row in rows:
        matrix[row["label"]][row["prediction"]] += 1

    per_class: dict[str, Any] = {}
    f1_values = []
    correct = 0
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[truth][label] for truth in LABELS if truth != label)
        fn = sum(matrix[label][pred] for pred in LABELS if pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(matrix[label].values()),
        }
        f1_values.append(f1)
        correct += tp

    unsafe = [row for row in rows if row["label"] != "complete"]
    premature = sum(row["prediction"] == "complete" for row in unsafe)
    return {
        "cases": len(rows),
        "accuracy": correct / len(rows) if rows else 0.0,
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "premature_completion_rate": premature / len(unsafe) if unsafe else 0.0,
        "premature_completion_count": premature,
        "non_complete_support": len(unsafe),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=Path(__file__).with_name("gold_v0.1.jsonl"))
    parser.add_argument("--url", default="http://127.0.0.1:8788/v1/workflows/completion-gate")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cases = [json.loads(line) for line in args.gold.read_text().splitlines() if line.strip()]
    predictions: list[dict[str, Any]] = []
    failures = Counter()
    started = time.perf_counter()
    for item in cases:
        request_id = item["id"]
        payload = {
            "task": item["task"],
            "current_result": item["current_result"],
            "execution_state": item["execution_state"],
            "request_id": request_id,
        }
        try:
            result = post_json(args.url, payload, args.timeout)
            prediction = result["decision"]
            if prediction not in LABELS:
                raise ValueError(f"invalid prediction: {prediction}")
            predictions.append(
                {
                    "id": item["id"],
                    "source": item["source"],
                    "label": item["label"],
                    "prediction": prediction,
                    "decision_source": result.get("decision_source"),
                    "reason": result.get("reason"),
                    "backend": result.get("backend"),
                    "latency_ms": result.get("latency_ms"),
                    "confidence": result.get("confidence"),
                }
            )
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            failures[type(error).__name__] += 1
            raise

    by_source = {
        source: metrics([row for row in predictions if row["source"] == source])
        for source in ("real", "synthetic")
    }
    report = {
        "benchmark": "completion-gate-v0.1",
        "gold_file": public_path(args.gold),
        "endpoint": args.url,
        "cases_total": len(cases),
        "source_counts": dict(Counter(row["source"] for row in cases)),
        "label_counts_by_source": {
            source: dict(Counter(row["label"] for row in cases if row["source"] == source))
            for source in ("real", "synthetic")
        },
        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
        "failures": dict(failures),
        "metrics_by_source": by_source,
        "predictions": predictions,
        "privacy": "no task/current_result bodies persisted in benchmark output",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"metrics_by_source": by_source, "cases_total": len(cases)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
