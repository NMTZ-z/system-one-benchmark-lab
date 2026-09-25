from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path

from run_model_tier_hard_fast import build_tasks


def post_json(base_url: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode())


def percentile(values: list[float], p: float) -> float:
    xs = sorted(values)
    if not xs:
        raise ValueError("empty")
    idx = min(len(xs) - 1, max(0, round((len(xs) - 1) * p)))
    return xs[idx]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument(
        "--output",
        default="results/processed/hermes-system-one-hard-fast-control-overhead-v0.1.json",
    )
    args = parser.parse_args()

    rows = []
    for rep in range(args.repetitions):
        for task in build_tasks():
            started = time.perf_counter()
            error = None
            search = tier = None
            try:
                search = post_json(
                    args.base_url, "/v1/workflows/search-gate", {"task": task["prompt"]}
                )
                tier = post_json(
                    args.base_url,
                    "/v1/workflows/model-tier-gate",
                    {"task": task["prompt"]},
                )
                ok = True
            except Exception as exc:  # noqa: BLE001
                ok = False
                error = type(exc).__name__
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            rows.append(
                {
                    "rep": rep,
                    "task": task["id"],
                    "category": task["category"],
                    "ok": ok,
                    "elapsed_ms": elapsed_ms,
                    "error": error,
                    "search_reason": search.get("reason")
                    if isinstance(search, dict)
                    else None,
                    "search_source": search.get("decision_source")
                    if isinstance(search, dict)
                    else None,
                    "tier": tier.get("tier") if isinstance(tier, dict) else None,
                    "tier_reason": tier.get("reason")
                    if isinstance(tier, dict)
                    else None,
                    "tier_source": tier.get("decision_source")
                    if isinstance(tier, dict)
                    else None,
                }
            )

    good = [r["elapsed_ms"] for r in rows if r["ok"]]
    hard_fast = [
        r
        for r in rows
        if r["tier"] == "fast"
        and r["tier_source"] == "rule"
        and r["tier_reason"] in {"bounded_transform", "bounded_structured_transform"}
    ]
    summary = {
        "runs": len(rows),
        "ok": len(good),
        "errors": len(rows) - len(good),
        "mean_ms": statistics.mean(good),
        "median_ms": statistics.median(good),
        "p95_ms": percentile(good, 0.95),
        "p99_ms": percentile(good, 0.99),
        "max_ms": max(good),
        "hard_fast_rule_rate": len(hard_fast) / len(rows),
        "method": {
            "tasks": len(build_tasks()),
            "repetitions": args.repetitions,
            "calls_per_run": ["search_gate", "model_tier_gate"],
            "measurement": "sequential HTTP wall time",
        },
        "rows": rows,
    }
    Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "runs",
                    "ok",
                    "errors",
                    "mean_ms",
                    "median_ms",
                    "p95_ms",
                    "p99_ms",
                    "max_ms",
                    "hard_fast_rule_rate",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
