"""Phase 8.2B offline verifier: no model, SDK, credentials or network calls.

Accepts one frozen privacy-safe JSON bundle or newline-delimited run/budget
records. Real task attestation must be produced by a separate private verifier.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

# Allow standalone execution from a source checkout without pip installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_system_one.budget_observability import BudgetError, reconcile_budget
from local_system_one.evidence_integrity import EvidenceError, verify_evidence

BUNDLE_SCHEMA = "local-system-one/verification-bundle-v1"
REPORT_SCHEMA = "local-system-one/verification-report-v1"


def read_bundle(path: Path) -> dict:
    if path.suffix == ".jsonl":
        runs, budgets = [], []
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != {"record_type", "data"}:
                raise ValueError(f"invalid JSONL record {index}")
            if row["record_type"] == "run":
                runs.append(row["data"])
            elif row["record_type"] == "budget":
                budgets.append(row["data"])
            else:
                raise ValueError(f"unknown record type at line {index}")
        bundle = {"schema": BUNDLE_SCHEMA, "runs": runs, "budgets": budgets}
    else:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict) or set(bundle) != {"schema", "runs", "budgets"}:
        raise ValueError("invalid bundle shape")
    if bundle["schema"] != BUNDLE_SCHEMA or not isinstance(bundle["runs"], list) or not isinstance(bundle["budgets"], list):
        raise ValueError("unsupported bundle version or collection")
    if len(bundle["runs"]) > 100 or len(bundle["budgets"]) > 100:
        raise ValueError("bundle run capacity exceeded")
    return bundle


def verify_bundle(bundle: dict) -> dict:
    if not isinstance(bundle, dict) or set(bundle) != {"schema", "runs", "budgets"} or bundle["schema"] != BUNDLE_SCHEMA:
        raise ValueError("unsupported bundle")
    evidence = [verify_evidence(run) for run in bundle["runs"]]
    ids = [item["run_id"] for item in evidence]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate run identifier")
    budgets = []
    for item in bundle["budgets"]:
        if not isinstance(item, dict) or set(item) != {
            "run_id", "records", "per_run_cap", "total_cap", "agent_reported_calls",
            "decision_calls", "usage_records", "controlled_egress_verified",
        }:
            raise ValueError("invalid budget entry shape")
        if item["run_id"] not in ids:
            raise ValueError("orphan budget entry")
        if not isinstance(item["controlled_egress_verified"], bool):
            raise ValueError("egress declaration must be explicit boolean")
        budgets.append(reconcile_budget(
            item["records"], run_id=item["run_id"], per_run_cap=item["per_run_cap"],
            total_cap=item["total_cap"], agent_reported_calls=item["agent_reported_calls"],
            decision_calls=item["decision_calls"], usage_records=item["usage_records"],
            controlled_egress_verified=item["controlled_egress_verified"],
        ))
    if len(set(row["run_id"] for row in budgets)) != len(budgets):
        raise ValueError("duplicate budget entry")
    budget_by_id = {row["run_id"]: row for row in budgets}
    comparisons: dict[str, dict] = {}
    groups = defaultdict(list)
    for row in evidence:
        groups[(row["platform"], row.get("task_case"))].append(row)
    for (platform, task), rows in groups.items():
        if task is None:
            continue
        modes = defaultdict(list)
        for row in rows:
            modes[row["mode"]].append(row)
        key = platform + ":" + task
        required = ("off", "shadow_healthy", "shadow_runtime_down")
        comparisons[key] = {
            "status": "AMBIGUOUS" if any(len(modes[m]) > 1 for m in required)
                      else "COMPLETE" if all(len(modes[m]) == 1 for m in required)
                      else "PARTIAL",
            "missing_modes": [m for m in required if m not in modes],
            "cases": {
                m: [{
                    "run_id": r["run_id"],
                    "task_outcome": r["task_outcome"],
                    "agent_execution_outcome": r["agent_execution_outcome"],
                    "evidence_integrity": r["evidence_integrity"],
                    "native_tool_calls": r["native_tool_calls"],
                    "native_tool_results": r["native_tool_results"],
                    "runtime_unavailable_events": r["runtime_unavailable_events"],
                    "observed_elapsed_ms": r["observed_elapsed_ms"],
                    "timing_source": r["timing_source"],
                    "provider_proxy_attempts": budget_by_id.get(r["run_id"], {}).get("proxy_attempts"),
                    "provider_responded": budget_by_id.get(r["run_id"], {}).get("provider_responded"),
                    "agent_reported_model_calls": budget_by_id.get(r["run_id"], {}).get("agent_reported_model_calls"),
                    "decision_runtime_calls": budget_by_id.get(r["run_id"], {}).get("decision_runtime_calls"),
                } for r in modes[m]]
                for m in required
            },
        }
    return {
        "schema": REPORT_SCHEMA,
        "runs": evidence, "budget_reconciliation": budgets,
        "run_comparisons": comparisons,
        "cross_platform_contract": (
            "PASS" if len({x["platform"] for x in evidence}) >= 3
            and all(x["evidence_integrity"] == "PASS" for x in evidence)
            else "BLOCKED"
        ),
        "methodology": "structural_offline_attestation_not_replay_of_private_task",
        "active_readiness": "NOT_AUTHORIZED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination")
    args = parser.parse_args()
    try:
        result = verify_bundle(read_bundle(args.bundle))
        encoded = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        else:
            print(encoded, end="")
        invalid = any(x["evidence_integrity"] == "BLOCKED" for x in result["runs"])
        invalid |= any(x["budget_integrity"] == "BLOCKED" for x in result["budget_reconciliation"])
        if invalid:
            raise SystemExit(2)
    except (EvidenceError, BudgetError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        # Errors do not echo private input paths, payloads or raw IDs.
        print(f"verification blocked: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
