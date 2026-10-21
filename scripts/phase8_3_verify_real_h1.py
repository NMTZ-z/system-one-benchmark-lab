#!/usr/bin/env python3
"""Independent PRIVATE evidence -> public allowlisted H1 verdict, no Provider I/O.

The original run is frozen at Git 8299347; verifier source can be newer.
Do not re-run an Agent or make up a provider terminal outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_system_one.budget_observability import reconcile_budget
from phase8_3_real_hermes_pilot import (
    ROOT, PRIVATE, RUN_ID, TEST_HOME, _independent_native_proof,
)

SOURCE_H1 = "82993477667817c8941caa429feea576d091a424"
H1_ORIGINAL_LEDGER_SHA = "bded2cecb79bcf22a6cdb39a4186b99fb68e881651d18142de370e3b120133de"
OUTPUT = ROOT / "results/processed/phase8_3_h1_real_stepfun_partial.json"


class H1EvidenceError(ValueError):
    pass


def _json_file(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise H1EvidenceError("invalid private H1 structured evidence")
    return result


def _ledger(path: Path) -> list[dict]:
    rows=[json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
          if line.strip()]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise H1EvidenceError("H1 ledger cannot be empty or malformed")
    if any(row.get("run") != RUN_ID for row in rows):
        raise H1EvidenceError("cross-run ledger contamination")
    return rows


def analyze(native: dict, private_summary: dict, records: list[dict], oracle: dict,
            *, evidence_hash: str) -> dict:
    if native.get("code_sha") != SOURCE_H1 or private_summary.get("source_sha") != SOURCE_H1:
        raise H1EvidenceError("original H1 source does not match frozen run")
    if (native.get("run_id") != RUN_ID or native.get("platform") != "hermes"
            or native.get("mode") != "off" or native.get("scenario") != "read_nonce"
            or native.get("main_model") != "stepfun/step-5-preview"):
        raise H1EvidenceError("invalid native source identity")
    if (native.get("process_exit_code") != 0 or native.get("timed_out") is not False
            or native.get("input_unchanged") is not True
            or native.get("read_proof",{}).get("final_answer_matches_nonce") is not True
            or native.get("gate_http_statuses") != []):
        raise H1EvidenceError("native read-only task not independently supported")
    if not oracle.get("valid") or not all(oracle.get(key) is True for key in (
        "native_read_result_paired",
        "original_file_matches_native_tool",
        "agent_final_matches_original_file",
        "native_provider_route_confirmed",
    )):
        raise H1EvidenceError("native SQLite/tool/file oracle is not independently proven")

    counts = reconcile_budget(
        records,
        run_id=RUN_ID,
        per_run_cap=3,
        total_cap=24,
        agent_reported_calls=native.get("usage",{}).get("api_calls"),
        decision_calls={"gate_requests":0,"rule_decisions":0,
                        "model_inferences":0,"failed_or_timed_out":0},
        controlled_egress_verified=True,  # pinned main route and native SQLite
    )
    if counts["proxy_attempts"] != 3 or counts["reserved_run"] != 3 or counts["reserved_total"] != 3:
        raise H1EvidenceError("exact H1 physical request count not proven")
    if native.get("provider_calls_counted_at_proxy") != 3 or (
        private_summary.get("transport",{}).get("attempted") != 3
    ):
        raise H1EvidenceError("original runner and provider budget observations disagree")
    if counts["agent_reported_model_calls"] != 2:
        raise H1EvidenceError("unexpected self-reported main model count")
    if private_summary.get("independent_native",{}).get("valid") is not True:
        raise H1EvidenceError("original independent native file proof missing")
    usage=native.get("usage",{})
    if usage.get("completed") is not True or usage.get("failed") is not False:
        raise H1EvidenceError("Agent did not independently complete its task")
    return {
        "schema": "local-system-one/phase8_3-real-native-h1-evidence-v1",
        "original_native_source_commit": SOURCE_H1,
        "platform": "hermes",
        "main_model": "stepfun/step-5-preview",
        "system_one_mode": "off",
        "scenario": "read_only_hidden_fixture",
        "provider_transport": "real_stepfun_step_plan_outbound_over_capped_proxy",
        "decision_model": "not_invoked_by_off_mode",
        "native_task": {
            "independent_tool_call_result_match": True,
            "original_file_bytes_verified": True,
            "agent_final_matches_file": True,
            "native_agent_exit_success": True,
            "task_result": "PASS_SCOPED",
        },
        "physical_request_budget": {
            "cap_global": 24,
            "cap_this_run": 3,
            "attempted": counts["proxy_attempts"],
            "provider_responded": counts["provider_responded"],
            "attempted_unresolved": counts["attempted_unresolved"],
            "proxy_unfinalized": counts["proxy_unfinalized"],
            "unattributed_requests": counts["unattributed_requests"],
            "budget_integrity": counts["budget_integrity"],
            "issues": counts["issues"],
        },
        "provider_response_codes": [
            row.get("http_status") for row in records if row.get("kind")=="responded"
        ],
        "source_native_reported_main_model_calls": counts["agent_reported_model_calls"],
        "source_native_reported_input_tokens": usage.get("input_tokens"),
        "source_native_reported_output_tokens": usage.get("output_tokens"),
        "provider_confirmed_token_spend": "NOT_MEASURED",
        "subscription_plan_debit": "UNKNOWN",
        "billing_currency_amount": "UNKNOWN",
        "private_budget_ledger_sha256": evidence_hash,
        "native_adapter_http_identity_link": "NOT_APPLICABLE_OFF",
        "phase8_3_real_native_acceptance": (
            "BLOCKED_BUDGET_RECONCILIATION" if counts["budget_integrity"]=="BLOCKED"
            else "PARTIAL_COST_UNKNOWN"
        ),
        "permission_to_run_more_provider_tasks": False,
        "active_authority": "NOT_AUTHORIZED",
        "benchmark_real_world_value": "NOT_ESTABLISHED",
        "real_agent_savings": "NOT_MEASURED",
    }


def historical_h1_ledger(archive: Path, current: Path) -> tuple[list[dict], str]:
    """Revalidate original 10 physical H1 records after future append-only runs.

    The historical 8.2A H1 report was produced from this exact immutable
    prefix before H2/H3 were run. Neither later Provider slots nor a
    synthesized outcome for missing slot 1 can enter H1 adjudication.
    The global Provider ledger MUST still contain the same first ten rows.
    """
    if archive.is_symlink() or current.is_symlink():
        raise H1EvidenceError("historical H1 ledger path is a symlink")
    if not archive.is_file() or not current.is_file():
        raise H1EvidenceError("historical H1 ledger or global original missing")
    raw=archive.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=H1_ORIGINAL_LEDGER_SHA:
        raise H1EvidenceError("original H1 immutable ledger hash mismatch")
    original_lines=raw.splitlines(keepends=True)
    global_lines=current.read_bytes().splitlines(keepends=True)
    if (len(original_lines)!=10 or len(global_lines)<10
            or b"".join(global_lines[:10])!=raw):
        raise H1EvidenceError("H1 records changed in the global physical ledger")
    return _ledger(archive),H1_ORIGINAL_LEDGER_SHA


def verify_private_h1() -> dict:
    root=PRIVATE
    ledger_path=root/"provider_h1_frozen.private.jsonl"
    ledger,ledger_digest=historical_h1_ledger(
        ledger_path,root/"provider_real_ledger.private.jsonl")
    native=_json_file(root/"runs/h1_read_off/verified_summary.private.json")
    private=_json_file(root/"runs/h1_verified.private.json")
    independent=_independent_native_proof()
    return analyze(native,private,ledger,independent,
                   evidence_hash=ledger_digest)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-public-aggregate",action="store_true")
    args=parser.parse_args()
    try:
        report=verify_private_h1()
        if args.write_public_aggregate:
            if OUTPUT.exists():
                raise H1EvidenceError("refusing to overwrite frozen real-run aggregate")
            OUTPUT.parent.mkdir(parents=True,exist_ok=True)
            OUTPUT.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,indent=2,sort_keys=True))
    except (H1EvidenceError,ValueError,OSError,TypeError,KeyError,AssertionError):
        print(json.dumps({"status":"BLOCKED","native_agent_requests":0,
                          "no_new_provider_requests":True}))
        raise SystemExit(3) from None


if __name__=="__main__":
    main()
