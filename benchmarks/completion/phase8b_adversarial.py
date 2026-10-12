#!/usr/bin/env python3
"""Fixed open adversarial challenge corpus. Never describe this as real blind validation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# Deliberately natural-language-only: execution_state={} for every case.
# These have not been sourced from private transcripts or used for threshold tuning.
CONTINUE = [
    ("Deploy the service to production.", "All staging deploy steps passed; production rollout is scheduled for tomorrow."),
    ("Publish the package in the public registry.", "Tag built and checked; registry publication has not yet started."),
    ("Merge the reviewed pull request.", "Approvals and green checks are present; the merge button has not been used."),
    ("Translate every resource into both languages.", "All English resources are completed; Chinese localization remains untranslated."),
    ("Run and pass all mandatory tests.", "Build finished and 99 tests passed, but the required 100th test fails."),
    ("Push all local changes to the remote repository.", "Local commit and checks are complete, but the git push has not run."),
    ("Run the dry-run and execute the actual rollout.", "Dry-run completed successfully; production rollout was cancelled."),
    ("Refund the customer and confirm the transfer.", "Refund request is accepted by the support desk but the payment processor has not sent funds."),
    ("Make a backup and perform a successful restore test.", "Backup archive and checksum passed, but the mandatory restore step is missing."),
    ("Rotate the API secret and revoke the old key.", "The new key works, but the old key has not been revoked."),
    ("Send the executive report to the team.", "Report drafted, polished and saved in drafts; no message has been sent."),
    ("Deliver a PDF file with the final charts.", "A PNG preview was generated, but no PDF artifact was created."),
    ("Repair the failed background daemon.", "Restart command exited successfully, but the daemon crashed immediately afterward."),
    ("Automate nightly metrics delivery.", "Scheduled trigger created, but the scheduled script does not exist."),
    ("Uninstall the old plugin completely.", "The plugin was disabled; its installation and plugin registry entry remain."),
]

VERIFY = [
    ("Verify the new release is publicly downloadable.", "A matching release tag exists locally; external download was not checked."),
    ("Confirm the changed configuration is active.", "Configuration file was updated, but the running server has not been queried."),
    ("Validate that the remote pull request was merged.", "A merge-style commit was found locally, but remote PR state is unconfirmed."),
    ("Confirm the published site is serving the new version.", "Deployment reported success, but the public URL was not fetched."),
    ("Confirm the object storage backup is recoverable.", "Upload has a success receipt, but no independent download checksum was checked."),
    ("Validate the hardware sensor pipeline.", "Collector status is green; destination telemetry time series has not been inspected."),
    ("Confirm the notifier sends messages to subscribers.", "Notification API accepted a test event, but client delivery is unconfirmed."),
    ("Verify that the final exported chart is valid.", "Chart export command completed, but the output has not been reopened."),
    ("Confirm the API key rotation succeeded across services.", "Secrets store reports the new key; downstream service integration remains unverified."),
    ("Confirm database migration has not lost data.", "Migration completed, but source and destination row counts were not reconciled."),
    ("Confirm the monthly report was received.", "The mail API returned 202 accepted; recipient delivery has not been confirmed."),
    ("Verify that release artifacts match the source build.", "Files are present, but the release checksum comparison has not been run."),
    ("Confirm the plugin is available to all users.", "Local manifest passed validation, but the external catalog was not checked."),
    ("Verify the firewall still permits required traffic.", "Policy deployment succeeded, but post-change allow/deny traffic probes are pending."),
    ("Confirm queue jobs finished without loss.", "Worker says all jobs complete, but dead-letter queue has not been reviewed."),
]

COMPLETE = [
    ("Deploy the service to production and verify it.", "Production was deployed, external health returned 200, and required smoke tests passed."),
    ("Publish the package and verify its contents.", "The public registry contains the version and a clean download matches its checksum."),
    ("Merge the approved pull request.", "Remote PR status confirms merged and main contains the expected commit."),
    ("Translate both locales and validate placeholders.", "Both locale files are delivered and each placeholder verification passed."),
    ("Run the complete required test suite.", "All mandated tests completed successfully and CI reports green."),
    ("Push the change to the remote repository.", "The remote branch contains the requested commit and independent fetch confirmed it."),
    ("Run dry-run and production rollout.", "Dry-run passed, production rollout succeeded, and live health was verified."),
    ("Issue the customer refund and confirm it.", "Payment processor confirms the refund settled and the customer was notified."),
    ("Back up the service and restore-test it.", "Backup and independent restore completed; checksums matched."),
    ("Rotate the API secret and revoke the old one.", "New key passes authorized probes and old key is independently confirmed revoked."),
    ("Send the executive report to the team.", "The report was delivered successfully and recipient mailboxes acknowledged delivery."),
    ("Deliver the PDF report with final charts.", "PDF exists at requested path, was reopened, and charts passed visual validation."),
    ("Repair the failed background daemon.", "The daemon stays running through its stability window and passes live probe."),
    ("Automate the nightly metrics report.", "Scheduled trigger and script executed in a trial and the report arrived."),
    ("Uninstall the old plugin entirely.", "Plugin files, registry entry and activation were removed; doctor shows no installation."),
]


def generate(path: Path) -> dict:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen challenge: {path}")
    rows = []
    for label, entries in (("complete", COMPLETE), ("continue", CONTINUE), ("verify", VERIFY)):
        for i, (task, result) in enumerate(entries):
            rows.append({
                "id": f"stress-{label}-{i:02d}",
                "source": "synthetic_adversarial",
                "provenance": "public_synthetic_text_only",
                "label": label, "task": task, "current_result": result, "execution_state": {},
            })
    blob = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(blob)
    return {"cases": len(rows), "sha256": hashlib.sha256(blob.encode()).hexdigest()}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(generate(a.out), indent=2))
