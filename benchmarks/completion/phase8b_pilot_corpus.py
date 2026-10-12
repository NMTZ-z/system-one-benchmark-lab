#!/usr/bin/env python3
"""Freeze an independent, *synthetic* Phase 8B pilot holdout.

The split uses disjoint task families. These are constructed workflows, not
actual Hermes/DSH production transcripts and NOT an Active-readiness proof.
Do not tune on the blind split, even though future releases may make it public.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# Each tuple: (task, verified result, unfinished result, unverified candidate).
# Different families in calibration and holdout prevent template-level leakage.
CALIBRATION = [
    ("Publish the library release", "The tagged artifact is available from the registry and the checksum matches.", "Package built locally, but publishing has not begun.", "Upload returned success, but registry listing was not checked."),
    ("Merge the patch into main", "The PR is merged and remote main contains the patch commit.", "The branch is ready, but no PR was opened.", "Merge command succeeded, but remote PR state is not yet confirmed."),
    ("Deploy the status API", "Endpoint returned 200 on the deployed host and the response schema passed validation.", "Service crashes on startup and no endpoint is running.", "Installer reported success, but no HTTP health request was sent."),
    ("Produce the monthly statement", "All required sections are present and finance signed off the final statement.", "Only income figures were calculated; the expense section is missing.", "The statement file exists, but required totals have not been reconciled."),
    ("Complete the database migration", "Migration applied and schema/data checks on the target database passed.", "Schema migration failed and was rolled back.", "Migration CLI returned zero but data row counts were not checked."),
    ("Submit the design handoff", "Design links were delivered, accessible, and acknowledged by the reviewer.", "Wireframes exist, but required accessibility variants are absent.", "Link was sent but recipients have not confirmed access."),
    ("Update the deployment manifest", "The requested fields are saved and schema validation passed on the target revision.", "Edits were staged but required validation fails.", "The editor showed success but the file was not re-read."),
    ("Finish the search indexing job", "Index contains the expected records and a representative query returned correct results.", "Indexing worker exited with an exception before writing records.", "Queue is empty but the query-level index check is pending."),
    ("Publish the documentation site", "Site URL opens with the new page and links all resolve.", "Markdown was written but the site was not built.", "Publish job is green but CDN cache may still have old content."),
    ("Run the API contract suite", "The full contract suite passed and the report was stored at the expected path.", "A required contract test fails with an assertion.", "Test command exited successfully but no report was preserved."),
    ("Deliver the encrypted backup", "Backup exists, restore test passed, and checksum matched.", "Backup file was generated but upload aborted.", "Backup was uploaded without a restore test."),
    ("Sync the translation resources", "Both locales were synchronized and placeholder checks passed.", "The second locale has not been translated.", "Sync command finished but untranslated string scan is pending."),
    ("Validate the model package", "Package loads in a clean runtime and expected outputs match fixtures.", "Conversion script stopped with a missing operator.", "Converter exported a package but it has not been loaded."),
    ("Register the plugin in the catalog", "Catalog entry is visible from a clean client and version matches the manifest.", "Local manifest is ready but registration was not submitted.", "Registry API accepted the request, but listing is not verified."),
    ("Archive the audit logs", "Required logs were archived in approved storage and retrieval was tested.", "Archive process skipped a required log segment.", "Archive job finished but storage retention settings are not verified."),
]

BLIND = [
    ("Configure event notifications", "A subscribed client received the expected test event and delivery was acknowledged.", "Webhook secret configured, but the subscription endpoint was never called.", "Provider accepted the subscription, but no delivery event was observed."),
    ("Restore a deleted workspace", "Restore completed and the recovered files passed byte-for-byte checksum comparison.", "Restore operation failed due to a missing snapshot.", "Restore command exited zero, but recovered files were not inspected."),
    ("Set up the scheduled report", "Scheduler ran at the required time and report was delivered to the target.", "Schedule entry exists but report generation command is missing.", "Scheduler reports success but delivery confirmation is unavailable."),
    ("Rotate an API credential", "Old credential was revoked and new credential passed an authorized test call.", "New key generated, but old key remains active despite required revocation.", "Rotation finished but downstream services have not been tested."),
    ("Verify hardware telemetry ingestion", "New sensor records arrived and their units and timestamps were validated.", "Telemetry collector still rejects the sensor's payload.", "Collector is running but the downstream time-series database was not checked."),
    ("Enable a feature switch for staging", "Staging process reports the intended flag value and smoke test succeeds.", "Flag key was created but the staging rollout was not performed.", "Control panel shows enabled but live staging behavior is unconfirmed."),
    ("Fix the download endpoint", "Fresh integration test downloaded the file and checksum matched expected bytes.", "The route was changed but downloads still return 500.", "Patch built successfully but no live download request was made."),
    ("Drain the worker queue", "Queue depth reached zero and every job has a terminal successful receipt.", "Worker restarted but the backlog remains unprocessed.", "Dashboard shows empty queue but dead-letter storage was not examined."),
    ("Create a reproducible notebook", "A clean kernel executed every cell and output snapshots matched.", "Notebook is written but execution stops on a missing dependency.", "Notebook executed once but saved outputs were not compared."),
    ("Move the static assets to object storage", "All files are reachable from new URLs and manifest hashes match.", "Upload skipped a required directory due to permission denied.", "CLI reports all uploaded but public download permissions were not checked."),
    ("Rebuild the mobile client", "Release build installed on a clean device and all required smoke checks passed.", "Only debug build succeeds; required signed build fails.", "Build artifact exists but clean device installation is pending."),
    ("Apply a firewall ruleset", "Expected allowed path works and denied path is blocked in network tests.", "Ruleset was drafted but not applied.", "Ruleset applied but post-change network probes were not executed."),
    ("Replay the event stream", "All expected records were consumed and idempotence checks found no duplicates.", "Replay crashed halfway, leaving the job incomplete.", "Replay reached offset target, but deduplication results have not been checked."),
    ("Mirror the Git repository to secondary storage", "Remote mirror includes target commit and independent clone resolves its tree.", "Local export finished but mirror push failed.", "Git push reported success but secondary fetch was not performed."),
    ("Confirm the compiled schema is compatible", "Generated client loads the schema and both backward-compatibility cases pass.", "Generation fails and no client artifact exists.", "Generator created files but compatibility tests were skipped."),
]


def _rows(families: list[tuple[str, str, str, str]], prefix: str) -> list[dict]:
    rows = []
    for i, (task, complete, unfinished, tentative) in enumerate(families):
        for label, result in (("complete", complete), ("continue", unfinished), ("verify", tentative)):
            state: dict = {}
            if label == "complete" and i % 3 == 0:
                state = {"required_checks_completed": True, "final_state_verified": True}
            if label == "continue" and i % 3 == 0:
                state = {"required_step_missing": True}
            elif label == "continue" and i % 3 == 1:
                state = {"tests_run": 3, "tests_passed": 2}
            if label == "verify" and i % 3 == 0:
                state = {"verification_required": True, "final_state_verified": False}
            elif label == "verify" and i % 3 == 1:
                state = {"conflicting_evidence": True}
            rows.append({
                "id": f"{prefix}-{i:02d}-{label}",
                "source": "synthetic_pilot",
                "provenance": "independent_curated_workflow",
                "label": label,
                "task": task,
                "current_result": result,
                "execution_state": state,
            })
    return rows


def freeze(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, families in (("calibration", CALIBRATION), ("blind", BLIND)):
        path = out_dir / f"phase8b-{name}-pilot-v1.jsonl"
        if path.exists():
            raise FileExistsError(f"immutable corpus already exists: {path}")
        rows = _rows(families, name)
        data = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
        path.write_text(data, encoding="utf-8")
        checksums[name] = {"sha256": hashlib.sha256(data.encode()).hexdigest(),
                           "count": len(rows), "families": len(families)}
    manifest = out_dir / "phase8b-pilot-freeze.json"
    if manifest.exists():
        raise FileExistsError(f"immutable manifest already exists: {manifest}")
    manifest.write_text(json.dumps({
        "version": "pilot-v1",
        "calibration": checksums["calibration"],
        "blind": checksums["blind"],
        "independent_final_acceptance": False,
        "reason": "synthetic pilot only, not real-agent blind benchmark",
    }, indent=2) + "\n")
    return checksums


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(freeze(args.out_dir), indent=2))


if __name__ == "__main__":
    main()
