#!/usr/bin/env python3
"""Replay a frozen private Hermes sample through the current Local System One policy.

The input file contains raw/private task text and must remain git-ignored.
Only aggregate summaries are intended for version control.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.error
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from replay_history import median, percentile, post_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-private", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()

    frozen = json.loads(args.input_private.read_text())
    if not isinstance(frozen, list):
        raise SystemExit("--input-private must contain a JSON list")

    input_sha256 = hashlib.sha256(args.input_private.read_bytes()).hexdigest()
    private_rows: list[dict[str, Any]] = []
    errors = 0
    started_all = time.perf_counter()

    for index, original in enumerate(frozen, 1):
        row = {
            key: value
            for key, value in original.items()
            if key not in {"search", "model_tier", "roundtrip_ms", "error"}
        }
        row.update(
            {
                "search": None,
                "model_tier": None,
                "roundtrip_ms": None,
                "error": None,
            }
        )
        started = time.perf_counter()
        try:
            row["search"] = post_json(
                args.base_url,
                "/v1/workflows/search-gate",
                {
                    "task": row["content"],
                    "context": row.get("context") or None,
                    "request_id": row["private_id"],
                },
                args.timeout,
            )
            row["model_tier"] = post_json(
                args.base_url,
                "/v1/workflows/model-tier-gate",
                {
                    "task": row["content"],
                    "context": row.get("context") or None,
                    "request_id": row["private_id"],
                },
                args.timeout,
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            TypeError,
            OSError,
        ) as exc:
            errors += 1
            row["error"] = type(exc).__name__
        row["roundtrip_ms"] = (time.perf_counter() - started) * 1000.0
        private_rows.append(row)
        if index % 25 == 0:
            print(f"replayed {index}/{len(frozen)} errors={errors}", flush=True)

    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(
        json.dumps(private_rows, ensure_ascii=False, indent=2)
    )

    valid = [row for row in private_rows if row["search"] and row["model_tier"]]
    confusion = Counter()
    search_reasons = Counter()
    search_backends = Counter()
    tier_counts = Counter()
    tier_backends = Counter()
    per_profile = defaultdict(Counter)
    per_source = defaultdict(Counter)
    roundtrips: list[float] = []
    gate_latencies: list[float] = []
    tool_counts_by_tier = defaultdict(list)
    span_by_tier = defaultdict(list)

    for row in valid:
        observed = bool(row["observed_public_lookup"])
        predicted = bool(row["search"].get("should_search"))
        key = (
            "tp"
            if observed and predicted
            else "fn_candidate"
            if observed and not predicted
            else "fp_candidate"
            if not observed and predicted
            else "tn"
        )
        confusion[key] += 1
        search_reasons[str(row["search"].get("reason"))] += 1
        search_backends[str(row["search"].get("backend"))] += 1
        tier = str(row["model_tier"].get("tier"))
        tier_counts[tier] += 1
        tier_backends[str(row["model_tier"].get("backend"))] += 1
        per_profile[row["profile"]][key] += 1
        per_profile[row["profile"]][f"tier_{tier}"] += 1
        per_source[row["source"]][key] += 1
        per_source[row["source"]][f"tier_{tier}"] += 1
        roundtrips.append(float(row["roundtrip_ms"]))
        gate_latencies.extend(
            float(value)
            for value in (
                row["search"].get("latency_ms"),
                row["model_tier"].get("latency_ms"),
            )
            if isinstance(value, (int, float))
        )
        tool_counts_by_tier[tier].append(int(row["tool_count"]))
        span_by_tier[tier].append(int(row["span_messages"]))

    tp = confusion["tp"]
    fn = confusion["fn_candidate"]
    fp = confusion["fp_candidate"]
    tn = confusion["tn"]

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    summary = {
        "generated_at": time.time(),
        "method": {
            "frozen_input": str(args.input_private),
            "frozen_input_sha256": input_sha256,
            "sample_size": len(frozen),
            "raw_content_committed": False,
            "private_output": str(args.private_output),
            "observed_public_lookup_is_weak_label": True,
        },
        "replay": {
            "valid": len(valid),
            "errors": errors,
            "elapsed_seconds": time.perf_counter() - started_all,
            "roundtrip_pair_ms": {
                "mean": statistics.fmean(roundtrips) if roundtrips else None,
                "p50": percentile(roundtrips, 0.50),
                "p95": percentile(roundtrips, 0.95),
                "max": max(roundtrips) if roundtrips else None,
            },
            "gate_model_latency_ms": {
                "p50": percentile(gate_latencies, 0.50),
                "p95": percentile(gate_latencies, 0.95),
            },
        },
        "search_behavior_alignment": {
            "confusion_vs_observed_tool_use": dict(confusion),
            "observed_lookup_recall": ratio(tp, tp + fn),
            "observed_no_lookup_specificity": ratio(tn, tn + fp),
            "precision_vs_observed_lookup": ratio(tp, tp + fp),
            "reasons": dict(search_reasons),
            "backends": dict(search_backends),
            "note": (
                "Behavioral alignment against historical weak labels, not correctness accuracy."
            ),
        },
        "model_tier": {
            "counts": dict(tier_counts),
            "backends": dict(tier_backends),
            "execution_complexity_proxy": {
                tier: {
                    "median_tool_calls": median([float(x) for x in values]),
                    "median_span_messages": median(
                        [float(x) for x in span_by_tier[tier]]
                    ),
                    "n": len(values),
                }
                for tier, values in tool_counts_by_tier.items()
            },
        },
        "by_profile": {key: dict(value) for key, value in sorted(per_profile.items())},
        "by_source": {key: dict(value) for key, value in sorted(per_source.items())},
        "private_review_candidates": {
            "false_no_search_candidates": fn,
            "false_search_candidates": fp,
            "stored_only_in_private_output": True,
        },
    }

    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
