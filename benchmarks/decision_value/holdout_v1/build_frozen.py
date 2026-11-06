#!/usr/bin/env python3
"""Write 80 PRE-LAYA authored, scenario-grounded offline fixtures.

This script and case specifications MUST be frozen in a Git commit before any
model is invoked on the cases. Synthetic oracle labels are pre-declared here,
not obtained from Gate outputs or fitted to model predictions.

No remote access, runtime inference, Agent execution, local private-data read,
API request, or production state mutation.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from local_system_one.workflows.completion_gate import CompletionGateRequest
from local_system_one.workflows.retry_escalation_gate import RetryEscalationRequest

HERE = Path(__file__).resolve().parent
SCHEMA = "local-system-one/new-holdout-case-v1"
SPLIT = "frozen_holdout"
# Public synthetic objects only, no private real task traces.
BASE_COMPLETION = {
    "tools_used": 1, "tool_failures": 0, "tests_run": 1, "tests_passed": 1,
    "artifacts_created": 1, "required_checks_completed": True,
    "final_state_verified": True,
}
BASE_RETRY = {
    "failure": {
        "category": "network", "transience": "transient", "outcome_known": True,
    },
    "operation": {
        "type": "read", "side_effect": "none", "idempotency": "verified",
        "side_effect_status": "none", "verified_idempotency_key": False,
        "reversibility": "yes", "metadata_source": "adapter_policy",
    },
    "history": {
        "attempts": 1, "max_attempts": 5, "repeated_failures": 0,
        "remaining_time_ms": 25000, "retry_budget_available": True,
    },
    "constraints": {
        "requires_approval": False, "alternative_available": False,
        "escalation_allowed": False, "escalation_budget_available": False,
    },
}

# Explicit editorial oracle: a controlled scenario's outcome, not an Agent's
# response and not the model's decision. No actual remote state is asserted.
# A=[acceptable labels], P=preferred. Multi-label cases are genuinely ambiguous.
# Every tuple is unique: (family, user task, reported result, state overrides,
# acceptable, preferred, independently specified fixture oracle explanation).
COMPLETION = [
    ("table_export", "Create a 3-column site inventory CSV and verify that each row has a valid key.",
     "The inventory file has all three columns; the isolated verifier checked 18 keyed rows and exact output bytes.",
     {}, ["complete"], "complete", "output_and_keys_verified"),
    ("monthly_brief", "Draft the monthly operations brief with five mandatory sections.",
     "Five sections were saved and a separate section-count check confirms all required material exists.",
     {"tools_used": 0, "tests_run": 0, "tests_passed": 0}, ["complete"], "complete", "required_sections_independently_checked"),
    ("unit_conversion", "Convert the six tabulated readings to the stated SI units and export the table.",
     "The exported table has six corrected readings; the independent conversion assertions all pass.",
     {"tests_run": 6, "tests_passed": 6}, ["complete"], "complete", "all_six_values_independently_verified"),
    ("documentation_patch", "Update a setup guide and verify that its three example commands still work.",
     "The requested edits are present and all three test commands passed after the patch.",
     {"tests_run": 3, "tests_passed": 3}, ["complete"], "complete", "commands_ran_and_passed"),
    ("json_schema", "Produce a JSON schema requiring device_id, unit, and timestamp.",
     "An independent validator accepted valid examples and rejected missing-field samples.",
     {"tests_run": 4, "tests_passed": 4}, ["complete"], "complete", "schema_properties_and_validation_verified"),
    ("data_cleanup", "Deduplicate the sample equipment register and preserve the newest record for each identifier.",
     "The resulting register has one row per identifier; independent assertions confirm selection order.",
     {"tests_run": 5, "tests_passed": 5}, ["complete"], "complete", "deduplication_postcondition_checked"),
    ("test_summary", "Write a test summary reporting actual passed and failed counts from the fixture suite.",
     "The summary matches the independent fixture test log for every test category.",
     {}, ["complete"], "complete", "source_counts_matched"),
    ("chart_spec", "Generate a plotting specification containing labeled axes and explicit engineering units.",
     "The chart specification includes both axes, unit strings and all mandatory series identifiers.",
     {"tools_used": 0, "tests_run": 0, "tests_passed": 0}, ["complete"], "complete", "required_plot_fields_checked"),
    ("local_index", "Create an index file linking four offline documents in the sample folder.",
     "All four link targets were independently checked to resolve inside the disposable fixture root.",
     {"tests_run": 4, "tests_passed": 4}, ["complete"], "complete", "all_local_references_resolved"),
    ("archive_manifest", "Write a manifest listing every file in the read-only sample archive.",
     "The final manifest entries exactly equal the independent directory listing and checksum set.",
     {}, ["complete"], "complete", "manifest_matches_fixture"),
    ("missing_appendix", "Produce a complete technical note with the required heat-balance appendix.",
     "The main note exists, but the requested heat-balance appendix has not been written.",
     {"required_artifact_missing": True, "final_state_verified": False},
     ["continue"], "continue", "mandatory_artifact_absent"),
    ("truncated_export", "Export 50 rows and deliver all 50 rows with their original identifiers.",
     "The operation returned success, but inspection shows that only 35 rows were written.",
     {"required_checks_completed": False, "final_state_verified": False},
     ["continue"], "continue", "fifteen_required_rows_missing"),
    ("invalid_calibration", "Fit the synthetic calibration curve and pass the fixed residual tests.",
     "The curve was fitted, but two of the five mandatory residual checks failed.",
     {"tests_run": 5, "tests_passed": 3, "final_state_verified": False},
     ["continue"], "continue", "required_validation_failed"),
    ("untouched_document", "Apply the approved edits to the second draft, not the original.",
     "A successful write was reported, but it affected the original rather than the required second draft.",
     {"blocking_failure": True, "final_state_verified": False},
     ["continue"], "continue", "wrong_target_document"),
    ("unfinished_multiturn", "Complete both phases: prepare a table, then validate it against the expected totals.",
     "The first phase generated the table; the second phase has not started.",
     {"required_step_missing": True, "final_state_verified": False},
     ["continue"], "continue", "second_phase_not_done"),
    ("partial_coverage", "Validate eight samples and report all eight results.",
     "Only five samples were evaluated; the remaining three were skipped.",
     {"required_checks_completed": False, "final_state_verified": False},
     ["continue"], "continue", "three_samples_not_validated"),
    ("broken_reference", "Update the markdown links and make sure each points to an existing file.",
     "One required link points to a nonexistent local target; the report says everything works.",
     {"tool_failures": 1, "blocking_failure": True, "final_state_verified": False},
     ["continue"], "continue", "link_target_missing"),
    ("unapplied_patch", "Change the fixture's tolerance to the approved threshold and test it.",
     "A suggested patch was printed, but the source file is still unchanged.",
     {"required_step_missing": True, "final_state_verified": False},
     ["continue"], "continue", "suggestion_not_applied"),
    ("failed_dependency", "Generate the packaging metadata and successfully build the sample package.",
     "Metadata exists, but package building exited with a dependency error.",
     {"tests_run": 1, "tests_passed": 0, "final_state_verified": False},
     ["continue"], "continue", "required_build_failed"),
    ("incorrect_unit", "Report the values in kPa with no unit mistakes.",
     "The response uses bar for half the numbers and no conversion was performed.",
     {"required_checks_completed": False, "final_state_verified": False},
     ["continue"], "continue", "engineering_units_wrong"),
    ("unsaved_response", "Save the complete five-step checklist as the deliverable file.",
     "The agent wrote a checklist in its answer, but the specified deliverable file does not exist.",
     {"required_artifact_missing": True, "final_state_verified": False},
     ["continue"], "continue", "answer_not_file_artifact"),
    ("interrupted_batch", "Process the complete sequence of 24 timestamped records.",
     "The tool stopped at the sixteenth record; it did not resume the remaining entries.",
     {"required_step_missing": True, "final_state_verified": False},
     ["continue"], "continue", "batch_interrupted"),
    ("external_write_unknown", "Submit a sample metadata update and confirm the final remote state.",
     "The client timed out after submission. The server response was not observed and final state is unknown.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "remote_effect_not_confirmed"),
    ("artifact_hash_unknown", "Deliver the generated checksum manifest and verify each checksum.",
     "A manifest is shown, but no independent rehash has been performed.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "independent_hash_check_pending"),
    ("untrusted_success_message", "Verify the fixture build and confirm that tests passed.",
     "The assistant says the build passed, but the command logs are unavailable to the verifier.",
     {"verification_required": True, "final_state_verified": False, "tests_run": 0, "tests_passed": 0},
     ["verify"], "verify", "model_claim_without_test_evidence"),
    ("delayed_result", "Wait for the isolated export job to finish and check its output.",
     "A job ID was returned but the result callback has not arrived.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "asynchronous_completion_unknown"),
    ("conflicting_hash", "Confirm the released file equals the signed fixture checksum.",
     "Two independently logged digests for the same file disagree.",
     {"conflicting_evidence": True, "final_state_verified": False},
     ["verify"], "verify", "conflicting_checksum_evidence"),
    ("stale_cache", "Confirm the published sample reflects the latest committed version.",
     "The local cache reports the new version, but the remote cache has not been checked.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "remote_cache_status_not_checked"),
    ("no_tool_visibility", "Determine if the locally requested file copy truly succeeded.",
     "A summary reports success without any native tool-result observation.",
     {"tools_used": 0, "tests_run": 0, "tests_passed": 0,
      "artifacts_created": 0, "final_state_verified": False},
     ["verify"], "verify", "native_tool_evidence_unavailable"),
    ("timestamp_conflict", "Confirm that the generated report covers the correct time range.",
     "One timestamp is in UTC and another has no offset; the reported range cannot be reconciled.",
     {"conflicting_evidence": True, "final_state_verified": False},
     ["verify"], "verify", "time_range_evidence_conflicts"),
    ("hidden_subtask", "Verify that an offline review task included the requested follow-up check.",
     "The final response is plausible, but the required follow-up test has no execution record.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "required_followup_unobserved"),
    ("ambiguous_approval", "Confirm the compliance checklist has the expected approval.",
     "A checked box appears in the report, but the approval signature and provenance are absent.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "approval_provenance_unknown"),
    ("partial_state_observed", "Check whether the disposable database migration finished.",
     "One table schema changed; the remaining migration state was not independently inspected.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "only_partial_db_state_observed"),
    ("incomplete_or_pending", "Ensure both result files are written before concluding.",
     "The first result exists; the second may still be produced by a running isolated worker.",
     {"final_state_verified": False, "required_checks_completed": True},
     ["verify", "continue"], "verify", "work_may_be_pending_or_incomplete"),
    ("flaky_validation", "Validate all readings using two independent fixtures.",
     "Fixture A passed; fixture B was not run because of an intermittent test environment error.",
     {"final_state_verified": False, "required_checks_completed": True},
     ["verify", "continue"], "verify", "environment_failure_distinct_from_task_failure"),
    ("unclear_requirement", "Prepare an operations diagram matching the requested scope.",
     "The diagram was produced, but the requirement did not specify whether an optional legend is mandatory.",
     {"final_state_verified": False, "required_checks_completed": True},
     ["verify", "continue"], "verify", "ambiguous_legend_acceptance"),
    ("pending_verification", "Compile the fixture report and check any reported anomalies.",
     "All sections are present but an anomaly flag has not been investigated.",
     {"verification_required": True, "final_state_verified": False},
     ["verify", "continue"], "verify", "anomaly_requires_followup_or_verification"),
    ("file_locked", "Save the updated document and verify the exact bytes.",
     "The editor reported a lock warning; a new output path may contain the correct copy.",
     {"final_state_verified": False, "required_checks_completed": True},
     ["verify", "continue"], "verify", "alternate_path_not_yet_checked"),
    ("two_turn_dependency", "Finish the multi-turn task only after the independent review has been received.",
     "The agent finished writing, but the reviewer's decision has not been observed.",
     {"verification_required": True, "final_state_verified": False},
     ["verify", "continue"], "verify", "reviewer_decision_pending"),
    ("stale_remote_receipt", "Confirm that the remote sample directory contains the newly exported log.",
     "The receipt identifier is present, but it predates the requested export and no current listing was captured.",
     {"verification_required": True, "final_state_verified": False},
     ["verify"], "verify", "old_receipt_does_not_prove_new_export"),
]

# Retry registry remains below. See the explicit author-approved scenario
# labels and fixture oracles before running a model.

# Explicit Retry editorial/fault-injection safe recommendation registry.
# (family, *trusted normalized failure/operation/history/constraint overrides*,
#  acceptable suggestions, preferred suggestion, controlled outcome rationale).
# Labels are choices among passive recommendations, not execution authority.
RETRY = [
    ("read_timeout_first", {"failure": {"category": "timeout"}, "history": {"attempts": 1}},
     ["retry_same"], "retry_same", "first_failure_verified_idempotent_read"),
    ("dns_blip_read", {"failure": {"category": "network"}, "history": {"attempts": 2, "max_attempts": 6}},
     ["retry_same"], "retry_same", "verified_read_transient_dns"),
    ("upstream_503_read", {"failure": {"category": "server_error", "http_status": 503}, "history": {"remaining_time_ms": 35000}},
     ["retry_same"], "retry_same", "temporary_upstream_503_on_read"),
    ("rate_limit_with_delay", {"failure": {"category": "rate_limit", "http_status": 429, "retry_after_ms": 1200}, "history": {"remaining_time_ms": 8000}},
     ["retry_same"], "retry_same", "bounded_retry_after_inside_remaining_time"),
    ("dual_safe_read", {"failure": {"category": "network"}, "history": {"attempts": 1},
                         "constraints": {"alternative_available": True}},
     ["retry_same", "try_alternative"], "try_alternative", "two_equally_safe_bounded_read_recoveries"),
    ("trusted_write_not_applied", {"failure": {"category": "server_error", "http_status": 502},
                                  "operation": {"type": "remote_api", "side_effect": "write",
                                                "side_effect_status": "not_applied",
                                                "idempotency": "verified",
                                                "verified_idempotency_key": True}},
     ["retry_same"], "retry_same", "separately_confirmed_nonexecution_with_verified_key"),
    ("alternate_after_unknown_transience", {"failure": {"category": "timeout", "transience": "unknown"},
                                             "constraints": {"alternative_available": True}},
     ["try_alternative"], "try_alternative", "safe_read_alternative_to_unproven_transience"),
    ("alternate_after_repeats", {"history": {"repeated_failures": 2, "attempts": 3},
                                  "constraints": {"alternative_available": True}},
     ["try_alternative"], "try_alternative", "repetition_cap_exceeded_and_safe_alternative_exists"),
    ("permanent_but_alternate", {"failure": {"category": "tool_error", "transience": "permanent"},
                                 "constraints": {"alternative_available": True}},
     ["try_alternative"], "try_alternative", "known_permanent_tool_issue_but_safe_alternative"),
    ("test_tool_alternate", {"failure": {"category": "test_failure", "transience": "unknown"},
                             "constraints": {"alternative_available": True}},
     ["try_alternative"], "try_alternative", "alternative_nonmutating_test_method_available"),
    ("remote_outcome_unknown", {"failure": {"category": "timeout", "outcome_known": False, "transience": "unknown"},
                                "operation": {"type": "remote_api", "side_effect": "external",
                                              "idempotency": "unknown",
                                              "side_effect_status": "unknown",
                                              "reversibility": "unknown"}},
     ["verify_state"], "verify_state", "remote_mutation_may_have_committed"),
    ("partial_git_push", {"failure": {"category": "network", "outcome_known": False, "transience": "unknown"},
                          "operation": {"type": "git_push", "side_effect": "external",
                                        "side_effect_status": "partial", "idempotency": "unknown",
                                        "reversibility": "unknown"}},
     ["verify_state"], "verify_state", "remote_refs_unknown_after_partial_push"),
    ("timeout_after_file_write", {"failure": {"category": "timeout", "outcome_known": False},
                                  "operation": {"type": "local_file", "side_effect": "write",
                                                "side_effect_status": "unknown",
                                                "idempotency": "unknown"}},
     ["verify_state"], "verify_state", "file_write_could_have_occurred"),
    ("unknown_side_effect_class", {"failure": {"category": "tool_error", "outcome_known": False, "transience": "unknown"},
                                   "operation": {"type": "unknown", "side_effect": "unknown",
                                                 "side_effect_status": "unknown",
                                                 "idempotency": "unknown",
                                                 "metadata_source": "unknown",
                                                 "reversibility": "unknown"}},
     ["verify_state"], "verify_state", "effect_type_and_commit_unknown"),
    ("partial_remote_receipt", {"failure": {"category": "partial_success", "outcome_known": False, "transience": "unknown"},
                                "operation": {"type": "remote_api", "side_effect": "external",
                                              "side_effect_status": "partial", "idempotency": "unknown"}},
     ["verify_state"], "verify_state", "receipt_present_but_state_partial"),
    ("auth_401", {"failure": {"category": "auth", "transience": "permanent", "http_status": 401}},
     ["ask_user"], "ask_user", "credentials_not_granted"),
    ("auth_403", {"failure": {"category": "auth", "transience": "permanent", "http_status": 403}},
     ["ask_user"], "ask_user", "permission_denied_by_server"),
    ("invalid_422", {"failure": {"category": "validation", "transience": "permanent", "http_status": 422}},
     ["ask_user"], "ask_user", "typed_payload_must_be_corrected"),
    ("rate_limit_over_delay", {"failure": {"category": "rate_limit", "http_status": 429, "retry_after_ms": 18000},
                               "history": {"remaining_time_ms": 3000}},
     ["ask_user"], "ask_user", "retry_after_exceeds_remaining_time"),
    ("rate_limit_repetition", {"failure": {"category": "rate_limit", "http_status": 429, "retry_after_ms": 500},
                               "history": {"repeated_failures": 3, "attempts": 4, "max_attempts": 7}},
     ["ask_user"], "ask_user", "repeated_rate_limit_not_eligible"),
    ("approval_required", {"constraints": {"requires_approval": True, "alternative_available": True}},
     ["ask_user"], "ask_user", "explicit_approval_missing"),
    ("budget_not_verified", {"history": {"retry_budget_available": False, "max_attempts": None}},
     ["ask_user"], "ask_user", "unverified_retry_budget"),
    ("nonretryable_400", {"failure": {"category": "tool_error", "http_status": 400, "transience": "permanent"}},
     ["ask_user"], "ask_user", "client_input_error_not_transient"),
    ("repeated_read_no_alternate", {"history": {"repeated_failures": 2, "attempts": 3}},
     ["ask_user"], "ask_user", "repeated_errors_without_safe_alternative"),
    ("untrusted_write_metadata", {"failure": {"category": "network", "transience": "unknown", "outcome_known": True},
                                  "operation": {"type": "remote_api", "side_effect": "write",
                                                "idempotency": "unknown", "side_effect_status": "not_applied",
                                                "metadata_source": "unknown"}},
     ["ask_user"], "ask_user", "untrusted_idempotency_precludes_repeat"),
    ("attempts_exhausted", {"history": {"attempts": 5, "max_attempts": 5}},
     ["abort"], "abort", "retry_count_at_limit"),
    ("time_budget_exhausted", {"history": {"remaining_time_ms": 0, "attempts": 2}},
     ["abort"], "abort", "time_remaining_zero"),
    ("applied_external_action", {"failure": {"category": "server_error", "outcome_known": True},
                                 "operation": {"type": "remote_api", "side_effect": "external",
                                               "idempotency": "unknown", "side_effect_status": "applied",
                                               "reversibility": "unknown"}},
     ["abort"], "abort", "already_applied_do_not_duplicate"),
    ("applied_git_push", {"failure": {"category": "tool_error", "transience": "unknown"},
                         "operation": {"type": "git_push", "side_effect": "external",
                                       "idempotency": "unknown", "side_effect_status": "applied"}},
     ["abort"], "abort", "ref_update_confirmed_applied"),
    ("permanent_no_alternative", {"failure": {"category": "logic_failure", "transience": "permanent"}},
     ["abort"], "abort", "no_safe_recovery_and_permanent_failure"),
    ("model_escalation_test", {"failure": {"category": "test_failure", "transience": "unknown"},
                               "constraints": {"escalation_allowed": True,
                                               "escalation_budget_available": True}},
     ["escalate_model", "ask_user"], "escalate_model", "preapproved_nonexecuting_model_escalation_recommendation"),
    ("model_escalation_logic", {"failure": {"category": "logic_failure", "transience": "unknown"},
                                "constraints": {"escalation_allowed": True,
                                                "escalation_budget_available": True}},
     ["escalate_model", "ask_user"], "escalate_model", "simulated_authorized_reasoning_tier_recommendation"),
    ("escalation_budget_missing", {"failure": {"category": "test_failure", "transience": "unknown"},
                                   "constraints": {"escalation_allowed": True,
                                                   "escalation_budget_available": False}},
     ["ask_user"], "ask_user", "escalation_budget_unavailable"),
    ("alternate_or_escalate", {"failure": {"category": "tool_error", "transience": "unknown"},
                               "constraints": {"alternative_available": True,
                                               "escalation_allowed": True,
                                               "escalation_budget_available": True}},
     ["try_alternative", "escalate_model"], "try_alternative",
     "two_policy_eligible_recovery_options"),
    ("permanent_alternative_or_abort", {"failure": {"category": "logic_failure", "transience": "permanent"},
                                        "constraints": {"alternative_available": True}},
     ["try_alternative", "abort"], "try_alternative", "alternative_exists_despite_permanent_original"),
    ("transient_read_or_ask", {"failure": {"category": "network", "transience": "transient"},
                               "constraints": {"alternative_available": False},
                               "history": {"attempts": 2, "max_attempts": 8}},
     ["retry_same", "ask_user"], "retry_same", "both_are_nonmutating_advice_when_budget_is_known"),
    ("rate_limit_no_retry_after", {"failure": {"category": "rate_limit", "http_status": 429, "retry_after_ms": None}},
     ["ask_user"], "ask_user", "retry_after_not_present"),
    ("write_not_applied_missing_key", {"failure": {"category": "network", "outcome_known": True, "transience": "unknown"},
                                       "operation": {"type": "remote_api", "side_effect": "write",
                                                     "idempotency": "verified", "side_effect_status": "not_applied",
                                                     "verified_idempotency_key": False}},
     ["ask_user"], "ask_user", "missing_reuse_key_even_if_idempotency_claimed"),
    ("nonidempotent_write_applied", {"failure": {"category": "tool_error", "transience": "unknown"},
                                    "operation": {"type": "pr_create", "side_effect": "external",
                                                  "idempotency": "non_idempotent", "side_effect_status": "applied",
                                                  "reversibility": "unknown"}},
     ["abort"], "abort", "nonidempotent_create_applied"),
    ("unverified_budget_and_alt", {"failure": {"category": "timeout", "transience": "unknown"},
                                   "history": {"retry_budget_available": False, "remaining_time_ms": None},
                                   "constraints": {"alternative_available": True}},
     ["ask_user"], "ask_user", "absence_of_preapproved_recovery_budget"),
]


def _canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _merge(base: dict, changes: dict) -> dict:
    result = copy.deepcopy(base)
    for key, val in changes.items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key].update(val)
        else:
            result[key] = val
    return result


def _historic_retry_inputs() -> set[bytes]:
    inputs: set[bytes] = set()
    for name in ("calibration", "holdout", "adversarial"):
        path = HERE.parents[1] / "retry" / f"{name}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            payload = dict(row["payload"])
            payload.pop("request_id", None)
            inputs.add(_canonical(payload))
    return inputs


def _historic_completion_text() -> set[bytes]:
    path = HERE.parents[1] / "completion" / "gold_v0.1.jsonl"
    return {
        _canonical({"task": row["task"], "current_result": row["current_result"],
                    "execution_state": row["execution_state"]})
        for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        for row in (json.loads(line),)
    }


def build() -> list[dict]:
    if len(COMPLETION) != 40 or len(RETRY) != 40:
        raise AssertionError("the preregistered 40+40 scenario matrix is incomplete")
    rows = []
    old_retry = _historic_retry_inputs()
    old_completion = _historic_completion_text()
    seen_inputs: set[bytes] = set()
    for idx, (family, task, reported, changes, acceptable, preferred, why) in enumerate(COMPLETION, 1):
        state = _merge(BASE_COMPLETION, changes)
        payload = {
            "task": task, "current_result": reported, "execution_state": state,
            "request_id": f"new-c{idx:03d}",
        }
        parsed = CompletionGateRequest.from_payload(payload)
        assert parsed.task == task and parsed.current_result == reported
        input_bytes = _canonical({k: v for k, v in payload.items() if k != "request_id"})
        if input_bytes in old_completion or input_bytes in seen_inputs:
            raise AssertionError(f"Completion fixture overlaps a previous case: {idx}")
        seen_inputs.add(input_bytes)
        rows.append({
            "schema": SCHEMA, "id": f"new-c{idx:03d}",
            "gate": "completion", "source": "synthetic",
            "split": SPLIT, "family": family, "input": payload,
            "gold": {"acceptable": acceptable, "preferred": preferred,
                     "oracle": "synthetic_editorial", "basis": why},
        })
    for idx, (family, changes, acceptable, preferred, why) in enumerate(RETRY, 1):
        payload = _merge(BASE_RETRY, changes)
        payload["request_id"] = f"new-r{idx:03d}"
        RetryEscalationRequest.from_payload(payload)
        input_bytes = _canonical({k: v for k, v in payload.items() if k != "request_id"})
        if input_bytes in old_retry or input_bytes in seen_inputs:
            raise AssertionError(f"Retry fixture overlaps a previous case: {idx}")
        seen_inputs.add(input_bytes)
        rows.append({
            "schema": SCHEMA, "id": f"new-r{idx:03d}",
            "gate": "retry_escalation", "source": "fault_injection",
            "split": SPLIT, "family": family, "input": payload,
            "gold": {"acceptable": acceptable, "preferred": preferred,
                     "oracle": "fault_oracle", "basis": why},
        })
    if len({r["family"] for r in rows}) != 80 or len({r["id"] for r in rows}) != 80:
        raise AssertionError("case families/IDs must be distinct")
    if any(not isinstance(r["gold"]["acceptable"], list) or
           not r["gold"]["acceptable"] or
           r["gold"]["preferred"] not in r["gold"]["acceptable"] for r in rows):
        raise AssertionError("invalid preregistered answer sets")
    if Counter(x["gate"] for x in rows) != {"completion": 40, "retry_escalation": 40}:
        raise AssertionError("unexpected gate allocation")
    return rows


def main() -> None:
    rows = build()  # no access to an inference output or saved predictions
    path = HERE / "new_frozen_holdout_v1.jsonl"
    path.write_bytes(b"".join(_canonical(item) + b"\n" for item in rows))
    print(json.dumps({
        "status": "AUTHOR_DEFINED_PRE_MODEL_UNSEALED",
        "cases": len(rows),
        "sources": dict(Counter(r["source"] for r in rows)),
        "gates": dict(Counter(r["gate"] for r in rows)),
        "input_digest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
