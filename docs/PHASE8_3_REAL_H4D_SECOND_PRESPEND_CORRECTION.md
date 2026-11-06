# H4D second pre-spend correction: eliminate DirectoryService at sandbox startup

**2026-10-26, before ANY actual H4D StepFun call.** Previous source
`8215a572be24b97110def542901796ed265507c6` and first preregistered
correction `8a433aca0f95c611e871462b86a7a5331914a490` are retained in
Git history. Neither was used to launch the real H4D Agent or paid proxy.
The ORIGINAL historical physical Provider ledger still hashes to
`5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`,
8/24 reservations, original H1 UNKNOWN=1. H4D run/recovery folders absent.

The first correction replaced the disposable service `HOME` with
`pwd.getpwuid(os.getuid())` to resolve the owner-global original ledger.
That OS user database call can raise `KeyError` inside a macOS Seatbelt
process using a deliberately blank isolated HOME. It would abort the proxy
before network egress, and made an unrelated legacy invalid-path test fail
with the wrong error. This is a real admission blocker, not a Provider
failure or invalid Agent decision.

In this second correction, the H4D orchestrator explicitly supplies
`PHASE83_H4D_OWNER_HOME` to its **only owned child service environment**.
It is an absolute canonical path, not a credential. The new H4D-specific
budget outlet rejects a missing or changed value; checks directory/UID,
symlink and canonical path before accepting it; requires the exact
unchanged old `Projects/system-one-phase8-3/private/phase8_3_native_real/
provider_real_ledger.private.jsonl` path; checks the original ledger SHA;
and retains original first-30-line fingerprint and per-run 3/24 global
reservation guards inside the fsynced exclusive lock. Non-H4D Provider
runs cannot invoke this special owner-global ledger branch.

A second test correction excludes the actual nested H4D kernel Seatbelt
exercise from the already Seatbelt-wrapped full Python suite. macOS
`Sandbox_apply` denies nesting when the parent sandbox does not authorize
such sandbox policy changes. This test must instead run in a distinct
synthetic-data process and exercise its own real kernel Seatbelt rules;
passing a fake/mock policy is not enough. The original five OS/kill tests
are likewise run separately with their own synthetic, bounded child scope.
All other non-OS-specific Python tests stay in the strict outer sandbox.

**Required acceptance before any paid trial:** fresh 100% scoped Python
and separate OS regressions, DSH Vitest/typecheck/build PASS, clean new
Git source commit and public privacy sanitizer PASS, updated Draft PR #12
with the **NEW** frozen hash, actual `--check-offline` against that hash,
unchanged 8/24 historical ledger and test Home OFF, independently confirmed
Step Plan credential PINNED_PROXY, no H4D case/recovery/logs. A failure
remains NO-GO, never trigger paid H4D as an error recovery mechanism.

No change to user-approved limit: genuine StepFun **Step Plan**
`step-5-preview` only, at most THREE new physical calls, one native
90-second task maximum, absolutely no PAYG/Active/autonomous retry.

## Verified correction results before updating the Draft

Under a credential-empty OS-sandboxed test HOME, fresh Python main
regression completed **1491 PASS, 2 SKIP, 6 separately deselected**. The six
OS/Seatbelt/child-process tests were independently executed on macOS with
synthetic fixtures and all **6/6 PASS**. DSH Vitest **64/64 PASS**, TypeScript
typecheck and build PASS. This correction modified **only** H4D-specific
physical budget proxy path resolution, test-only parent environment, an
unrelated safety-test input and this document. Original Hermes/DSH plugin,
Runtime and Gate behavior were not modified.

The old original historical physical ledger remains unchanged at 8/24,
with the H1 UNKNOWN retained. The new H4D case and rollback folders were
still nonexistent at this verification stage. The existing 90-second
one-task/three-physical-call/no-PAYG/zero-automatic-retry permission is not
increased by a fix to the environmental guard.
