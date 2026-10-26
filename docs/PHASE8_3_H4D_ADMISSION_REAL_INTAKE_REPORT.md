# Phase 8.3 — H4D zero-cost admission + real decision evidence intake

**Date: 2026-10-26. Real H4D: BLOCKED BEFORE EXECUTION.** This is a
read-only preparation/audit package stacked on Phase 8.3 stock-shell Shadow
PR #10. No official credentials were read, no Agent/Provider request was
started, and no paid StepFun calls, Active/Canary, retries or production
configuration changes occurred.

## 1. Frozen source and evidence

The original parent commit is `e971889e23ecae6db54712c43772eb670c0a068d`.
The protocol, two audit implementations and their original negative
regression tests were committed **before their formal read-only assessment**
as `d2af2e01e033be727dacf8bbbc826ca02475d37c`. A later unit-test-only
change replaced reliance on the host's actual HOME with a synthetic
isolated credential fixture. The two original read-only output reports
were preserved, not overwritten or retroactively reclassified.

The read-only H4D preflight verified a clean frozen checkout, six exact
Hermes original source-file hashes in the credential-free export from
`4d04303818b61bf3aa09278af48356315515965b`, locally cached pinned
Laya 421M weight digest, original private Provider ledger SHA-256 and the
existing test Home's NONSECRET static OFF config. It called ONLY
`inspect(official_auth=False)` for that last operation. A credential file
may exist in the earlier isolated test Home, but **its contents, authority,
actual route and remaining Plan credit were not checked**. Installed Hermes
has advanced beyond the frozen source, so it must not be silently swapped
for the verified archive in any subsequent trial.

Public bounded [H4D readiness result](../results/processed/phase8_3_h4d_offline_readiness.json):
`offline_readonly_engineering_preconditions=PASS_SCOPED` and
**`real_H4D_qualification=BLOCKED_PRE_EXECUTION`**. The admission checker
has no real native-run entrypoint, no Proxy connector and no request
authorization write path.

## 2. Actual historical real-Agent data inventory

Three original publicly reported Hermes + real StepFun tests, H1/H2/H3,
were audited **only through their frozen public processed aggregates**;
original private task transcripts and raw Provider records were NOT reread.
Each public original was checked against its exact preregistered SHA-256.

| Published original | Original scoped native result | Physical Provider requests | Actual new decision evidence for incremental value |
|---|---|---:|---|
| H1 (OFF) | Native read success, published independent proof | 3: 2 HTTP 200, 1 outcome UNKNOWN | No local model or independent decision label |
| H2 (Shadow) | Native read success, two observed local Laya Completion decisions and exact HTTP correlation | 3 terminal HTTP 200 | Two real *advisory observations*, but no independently adjudicated decision gold |
| H3 (Runtime down) | Native read success, two HTTP 503 and fail-open observations | 2 terminal HTTP 200 to Provider | Zero Laya predictions during failure; no independent paired decision gold |

**Totals:** historical scoped task successes **3**, genuine local decision
observations **2**, independently adjudicated real decision-gold count **0**,
and eligible same-input Rule-only-versus-Laya *real accuracy* pairs **0**.
This is NOT a 0% Laya accuracy claim: the denominator for a defensible
real-world accuracy comparison is absent. Four previously successful
stock-shell native tasks with a **synthetic main Provider** are expressly
excluded from the real Agent denominator.

Provider accounting remains **8/24 physical attempts, seven recorded
HTTP 200 and one original H1 UNKNOWN**. The exact original ledger digest
was independently rechecked, unchanged at
`5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`.
Unknown outcome and unknown Plan/billed usage cannot be promoted to success,
free calls or savings.

Public bounded [real evidence feasibility JSON](../results/processed/phase8_3_real_evidence_feasibility.json)
preserves this distinction. It is based on three historical publications,
not new model execution or re-adjudication of their private raw evidence.

## 3. Real H4D execution remains gated

These **separate nontechnical approvals and verifications** are required:

1. A new explicit H4D owner authorization identifying StepFun Step Plan
   `step-5-preview`, a hard per-case **physical request ceiling** (proposed
   maximum 3), one-shot **time ceiling** (proposed 90 seconds) and a
   specified billing/Plan-credit safety condition. The original 16 nominal
   unused places in a historical 24-cap do NOT constitute permission.
2. Fresh owner-controlled official isolated Hermes authentication, full
   proof that every main/pooled/auxiliary Provider endpoint traverses the
   request-counting loopback proxy. No existing credential is inferred
   usable from a file's mere existence; no production credential clone.
3. Freeze a new distinct H4D **single-run native executor**, exact Hermes
   source/interpreter, protected original absent-file manifest, local model
   version, independent SQLite error/Shadow oracle, Provider reservation
   ledger extension rules, process ownership recovery, OS Seatbelt denies
   and hard stop conditions BEFORE any real outbound request.
4. No automatic retry, no Active, no Agent tool write, no production
   Gateway restart or modification, no Provider egress until ALL real-case
   admission checks are green. Preserve H1 UNKNOWN and all originals.

**Engineering recommendation:** treat PR #9 / #10 as completed *offline*
engineering deliverables and keep them Draft. The real H4D decision remains
NO-GO until separately authorized and frozen, then should be done once
under its own strict physical request budget and independent native oracle.
Decision-value accuracy and actual savings remain NOT_ESTABLISHED /
NOT_MEASURED. A next independent sample protocol is the earlier
[real value admission document](PHASE8_3_REAL_VALUE_FOLLOWUP_ADMISSION.md):
collect consecutive safe real decision opportunities, independently label
gold, preserve equal rules across B/C and report no claimed value if the
true real eligible sample remains zero. The next phase is not 8D Active.

## 4. Engineering QA and publication controls

The original pre-freeze functional negative tests passed **25/25**. A new
synthetic credential-not-read test brings the focused total to **26 PASS**.
The first full run had **1482 PASS, 1 environment-fixture failure,
2 intentional SKIPs and 5 separate OS tests**: its credential-read test
incorrectly assumed the real owner's `~/.hermes` would exist *inside* the
outer sandbox, whose HOME was deliberately empty. We replaced that single
test fixture with a synthetic 0600 `auth.json` and mocked data-root scope,
then verified that the **actual static inspection implementation** never
opened the synthetic credential. Production auth handling, Gate rules,
Provider route or permissions were not changed.

Fresh post-repair full Python main suite: **1483 PASS / 2 SKIP /
5 separately deselected**, with **5/5** real OS/Seatbelt and process-group
safety tests and **1/1** pinned official Hermes tool-registry test separately
PASS. The original optional private-ledger fixture remains deliberately
unmounted in full regression; its SHA was independently rechecked by the
new read-only audit instead. DSH tests: **64/64 Vitest PASS**, TypeScript
typecheck PASS and build PASS, no DSH source code changes. macOS Seatbelt
may report test-worker shutdown `EPERM`; completed Vitest returned exit 0.

Final public allowlist sanitizer and independent SHA-256 manifest check must
pass on a clean publication commit. All passwords, original native Session
identifiers, raw transcripts, test-Home auth, old physical ledger rows,
private recovery files and model weights are excluded from the public
bundle. No system-wide package update, live Provider request, Gateway
restart, Active mode or automatic merge is part of this audit.
