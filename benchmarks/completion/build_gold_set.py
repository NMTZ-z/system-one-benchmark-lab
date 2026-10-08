#!/usr/bin/env python3
"""Build the public Phase 8A Completion Gate gold set.

The ``real`` slice is a privacy-safe reconstruction of public repository tasks
and outcomes. It is intentionally not a dump of private Agent transcripts.
Synthetic cases broaden boundary coverage while remaining separately labeled.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("gold_v0.1.jsonl")


def case(
    case_id: str,
    source: str,
    label: str,
    task: str,
    current_result: str,
    execution_state: dict,
    *,
    provenance: str,
) -> dict:
    return {
        "id": case_id,
        "source": source,
        "provenance": provenance,
        "label": label,
        "task": task,
        "current_result": current_result,
        "execution_state": execution_state,
    }


REAL = [
    case("real-complete-01", "real", "complete", "Confirm Phase 7B is merged to GitHub main.", "GitHub main contains merge commit 2b2b114 and the Adapter Contract files are present on main.", {"required_checks_completed": True, "final_state_verified": True}, provenance="public_repo_reconstructed"),
    case("real-complete-02", "real", "complete", "Validate the DeepSeek Harness adapter build before release.", "The adapter test suite, TypeScript typecheck, and production build all passed.", {"tests_run": 3, "tests_passed": 3, "required_checks_completed": True}, provenance="public_repo_reconstructed"),
    case("real-complete-03", "real", "complete", "Verify the Hermes plugin manifest version and hooks.", "Manifest parses successfully, expected version is present, and all declared lifecycle hooks match the implementation.", {"tests_run": 2, "tests_passed": 2, "required_checks_completed": True}, provenance="public_repo_reconstructed"),
    case("real-complete-04", "real", "complete", "Check that the local System One service is healthy.", "The loopback health endpoint returned service=ok and ANE state=healthy.", {"required_checks_completed": True, "final_state_verified": True}, provenance="public_repo_reconstructed"),
    case("real-complete-05", "real", "complete", "Create and validate the adapter contract JSON schema.", "The schema file exists, parses as JSON, and contract tests pass.", {"artifacts_created": 1, "tests_run": 2, "tests_passed": 2, "required_checks_completed": True}, provenance="public_repo_reconstructed"),
    case("real-complete-06", "real", "complete", "Confirm Search, Model Tier, and Notification regression behavior.", "All existing Python and adapter regression tests covering the three gates passed without behavior changes.", {"tests_run": 3, "tests_passed": 3, "required_checks_completed": True}, provenance="public_repo_reconstructed"),
    case("real-complete-07", "real", "complete", "Verify the public benchmark result artifact.", "The result JSON was generated, re-read successfully, and contains the required metrics and confusion matrix.", {"artifacts_created": 1, "required_checks_completed": True, "final_state_verified": True}, provenance="public_repo_reconstructed"),
    case("real-complete-08", "real", "complete", "Confirm the Completion endpoint contract.", "POST /v1/workflows/completion-gate returned 200 with a valid complete/continue/verify response and malformed requests returned 400.", {"tests_run": 2, "tests_passed": 2, "required_checks_completed": True}, provenance="public_repo_reconstructed"),
    case("real-complete-09", "real", "complete", "Verify privacy-safe Completion telemetry.", "Tests confirm telemetry stores decision metadata and lengths but does not persist raw task or result bodies.", {"tests_run": 2, "tests_passed": 2, "required_checks_completed": True}, provenance="public_repo_reconstructed"),
    case("real-complete-10", "real", "complete", "Check fail-open behavior for a dead Completion service.", "Hermes and DSH dead-service tests passed and native platform execution remained unaffected.", {"tests_run": 2, "tests_passed": 2, "required_checks_completed": True}, provenance="public_repo_reconstructed"),

    case("real-continue-01", "real", "continue", "Finish Phase 8A and run the Python regression suite.", "Implementation is present, but one required Python test is still failing.", {"tests_run": 49, "tests_passed": 48}, provenance="public_repo_reconstructed"),
    case("real-continue-02", "real", "continue", "Validate the DSH adapter for release.", "Unit tests passed, but TypeScript typecheck failed.", {"tests_run": 2, "tests_passed": 1}, provenance="public_repo_reconstructed"),
    case("real-continue-03", "real", "continue", "Publish the Completion Gate documentation.", "Runtime code is complete, but docs/COMPLETION_GATE.md has not been created.", {"required_artifact_missing": True}, provenance="public_repo_reconstructed"),
    case("real-continue-04", "real", "continue", "Push the completed Phase 8A branch to GitHub.", "All local tests pass, but no git push has been executed yet.", {"required_step_missing": True}, provenance="public_repo_reconstructed"),
    case("real-continue-05", "real", "continue", "Verify the local service endpoint after starting it.", "The process start command returned, but the endpoint request failed with connection refused.", {"blocking_failure": True}, provenance="public_repo_reconstructed"),
    case("real-continue-06", "real", "continue", "Build the DeepSeek Harness plugin package.", "Source edits are complete, but npm run build has not been run.", {"required_checks_completed": False}, provenance="public_repo_reconstructed"),
    case("real-continue-07", "real", "continue", "Finish both platform adapters for Completion Shadow.", "Hermes is integrated, but the DSH adapter still lacks Completion handling.", {"required_step_missing": True}, provenance="public_repo_reconstructed"),
    case("real-continue-08", "real", "continue", "Create the Completion benchmark report.", "Gold set exists, but benchmark execution stopped before metrics were produced.", {"required_artifact_missing": True}, provenance="public_repo_reconstructed"),
    case("real-continue-09", "real", "continue", "Validate GitHub CI after pushing Phase 8A.", "The workflow is running and one required job is currently red.", {"blocking_failure": True, "required_checks_completed": False}, provenance="public_repo_reconstructed"),
    case("real-continue-10", "real", "continue", "Finish the requested runtime tests.", "Complete and continue cases were added, but verify and malformed-request coverage are still missing.", {}, provenance="public_repo_reconstructed"),

    case("real-verify-01", "real", "verify", "Confirm a local commit reached GitHub main.", "A local commit exists and push reported success, but remote main has not been fetched or inspected.", {"verification_required": True, "final_state_verified": False}, provenance="public_repo_reconstructed"),
    case("real-verify-02", "real", "verify", "Confirm the service deployment is healthy.", "The installer exited successfully, but /health has not been queried after installation.", {"verification_required": True, "final_state_verified": False}, provenance="public_repo_reconstructed"),
    case("real-verify-03", "real", "verify", "Confirm a GitHub pull request is merged.", "A merge-looking commit was found locally, but the PR state and remote main were not independently checked.", {"verification_required": True, "final_state_verified": False}, provenance="public_repo_reconstructed"),
    case("real-verify-04", "real", "verify", "Create the required documentation file and confirm contents.", "The write command succeeded, but the file has not been re-read or parsed.", {"verification_required": True, "final_state_verified": False}, provenance="public_repo_reconstructed"),
    case("real-verify-05", "real", "verify", "Confirm the plugin appears in the external catalog.", "The local plugin metadata is correct, but the external catalog state has not been observed.", {}, provenance="public_repo_reconstructed"),
    case("real-verify-06", "real", "verify", "Confirm a model upload is publicly downloadable.", "Upload returned an artifact URL, but a clean download and checksum verification have not been performed.", {"verification_required": True, "final_state_verified": False}, provenance="public_repo_reconstructed"),
    case("real-verify-07", "real", "verify", "Determine whether the release is healthy.", "Local health is green, but a remote status signal reports the service unavailable.", {"conflicting_evidence": True}, provenance="public_repo_reconstructed"),
    case("real-verify-08", "real", "verify", "Validate the benchmark result before publication.", "Metrics were produced, but the confusion matrix and source-split counts have not been cross-checked.", {}, provenance="public_repo_reconstructed"),
    case("real-verify-09", "real", "verify", "Confirm the package version users will install.", "package.json says 0.5.0, but the built package metadata has not been inspected.", {"verification_required": True, "final_state_verified": False}, provenance="public_repo_reconstructed"),
    case("real-verify-10", "real", "verify", "Confirm the endpoint is ready for real adapters.", "A unit test got a valid response, but the live service process has not been exercised with the new endpoint.", {}, provenance="public_repo_reconstructed"),
]


COMPLETE_TASKS = [
    ("Create report {i} and validate the required sections.", "Report {i} exists, all required sections are present, and validation passed."),
    ("Confirm repository state for change {i}.", "Remote main contains change {i}, the expected file is present, and the check completed successfully."),
    ("Export artifact {i} and verify it.", "Artifact {i} was exported, re-opened successfully, and its checksum matched."),
]
CONTINUE_TASKS = [
    ("Finish implementation task {i}.", "The code was edited, but a required test is still failing."),
    ("Deliver artifact {i}.", "Only the first half of artifact {i} is complete; the required final output is missing."),
    ("Complete deployment {i}.", "The deployment command failed before the service started."),
]
VERIFY_TASKS = [
    ("Confirm publication state {i}.", "A candidate publication record exists, but the final public state has not been independently checked."),
    ("Confirm deployment state {i}.", "The deployment command reported success, but no health check has been run."),
    ("Validate result {i}.", "A plausible result exists, but two pieces of evidence disagree and need reconciliation."),
]


def synthetic_cases() -> list[dict]:
    rows: list[dict] = []
    for label, templates in (
        ("complete", COMPLETE_TASKS),
        ("continue", CONTINUE_TASKS),
        ("verify", VERIFY_TASKS),
    ):
        for i in range(1, 31):
            task_template, result_template = templates[(i - 1) % len(templates)]
            state: dict = {}
            if label == "complete":
                state = {"required_checks_completed": True, "final_state_verified": True}
            elif label == "continue":
                if i <= 5:
                    state = {"tests_run": 4, "tests_passed": 3}
                elif i <= 10:
                    state = {"required_artifact_missing": True}
                elif i <= 15:
                    state = {"blocking_failure": True}
                elif i <= 20:
                    state = {"required_step_missing": True}
                # 21-30 intentionally model-only.
            else:
                if i <= 10:
                    state = {"verification_required": True, "final_state_verified": False}
                elif i <= 20:
                    state = {"conflicting_evidence": True}
                # 21-30 intentionally model-only.
            rows.append(
                case(
                    f"synthetic-{label}-{i:02d}",
                    "synthetic",
                    label,
                    task_template.format(i=i),
                    result_template.format(i=i),
                    state,
                    provenance="phase8a_template",
                )
            )
    return rows


def main() -> int:
    rows = REAL + synthetic_cases()
    assert len(rows) == 120
    for source in ("real", "synthetic"):
        selected = [row for row in rows if row["source"] == source]
        labels = {label: sum(row["label"] == label for row in selected) for label in ("complete", "continue", "verify")}
        assert all(labels.values()), (source, labels)
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    print(f"wrote {len(rows)} cases to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
