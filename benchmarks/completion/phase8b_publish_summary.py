#!/usr/bin/env python3
"""Export strictly aggregate-only Phase 8B pilot statistics, never private inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_SETS = ("cal", "blind", "stress")
POLICIES = ("8a", "rules", "raw", "candidate")


def public_summary(private_dir: Path) -> dict:
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
        policies = {}
        for key in POLICIES:
            metrics = source["policies"][key]
            policies[key] = {
                "accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "per_class": metrics["per_class"],
                "confusion_matrix": metrics["confusion_matrix"],
                "premature_completion_count": metrics["premature_completion_count"],
                "non_complete_support": metrics["non_complete_support"],
                "premature_completion_wilson_95": metrics["premature_completion_wilson_95"],
            }
        report["sets"][name] = {
            "cases": source["matched_case_count"],
            "classes": ["complete", "continue", "verify"],
            "policies": policies,
            "warnings": [
                "synthetic engineered cases, not genuine Hermes/DSH Agent traces",
                "calibration and blind are disjoint families but not production-grade evidence",
                "raw has no stop authority; candidate threshold has no production effect",
            ],
        }
    freeze = json.loads((private_dir / "phase8b-pilot-freeze.json").read_text())
    report["freeze_sha256"] = {
        "calibration": freeze["calibration"]["sha256"],
        "blind": freeze["blind"]["sha256"],
        "stress": "fa7324fcee611988c9ed3f92d6a0ac1f7af81b9b22c2fcb219f86dbc22856b2b",
    }
    for phase in ("cal", "blind"):
        reliability = json.loads((private_dir / f"phase8b-{phase}-reliability.json").read_text())
        report["sets"][phase]["model_only_reliability"] = reliability
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
