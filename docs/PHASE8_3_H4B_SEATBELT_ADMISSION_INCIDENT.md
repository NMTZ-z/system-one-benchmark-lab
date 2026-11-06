# Phase 8.3A — H4B Seatbelt admission blocker and verified local rollback

**Executed 2026-10-23, frozen REAL source:
633c914fe9b78b7515cfcfbe4795f5d2dbd3aadf.**

**Original H4B result: BLOCKED BEFORE AIAgent construction.
Zero H4B StepFun Provider requests. Successful test-Home rollback.**
This report is written AFTER the original run and is NOT the frozen
execution source. H4B is not a real native missing-file / Retry PASS.

## 1. The owner-safety requirement was enforced

H4B was a NEW case following the earlier H4 Gateway-conflict refusal.
The owner explicitly prioritized that no permanent production
environment effects occur. H4B's preregistered source therefore used:
- official in-process Hermes run_oneshot, not the production Gateway;
- a separate, previously authenticated Hermes test Home;
- a macOS Seatbelt sandbox on the native child;
- only a single read_file tool and the exact preregistered absent path;
- only localhost 18793/18794 network ports for observer/Provider cap;
- a durable pre-run SQLite/plugin/config/source snapshot, with no
  API-token contents included in the backup;
- OS-owned process group cleanup and separate PID/UID/start-time
  identity records to avoid killing unrelated production processes;
- the original global physical Provider cap, never reset.

All 1307 Python tests and 64 DSH tests passed before the real attempt;
TS typecheck and build passed. Source was frozen and pushed to the
Draft PR #9 as 633c914, with a 309-file clean public release
sanitizer marked publish_ready=true. Before the attempt, an
offline, all-network-denied Seatbelt import of real Hermes
run_oneshot and a one-read_file toolset completed successfully.
That import-only preflight did NOT exercise the full one-shot
startup/prompt I/O path. This gap is the central regression found.

## 2. Exactly what happened

The new H4B orchestrator took the private baseline recovery snapshot,
created a NEW disposable H4B absent-file manifest, switched ONLY its
test Home to Shadow, and launched test-only Laya/MLX, HTTP Observer
and StepFun hard-cap proxy processes. The OS Seatbelt-protected
native process then entered the official Hermes run_oneshot function.

**It failed BEFORE constructing AIAgent** with a genuine macOS
PermissionError from Hermes trying to open /dev/null to suppress
ordinary stdout/stderr during the one-shot. The original OS policy
deliberately denied all writes except isolated test SQLite/plugin
state and the disposable case folder, so opening this harmless
system device for writing was not permitted.

This was not a Provider error, a failed native read_file result,
a model inference failure, or a System One Retry Gate outcome.
No native Session/Tool call was created, no real Completion/Retry
HTTP observer events occurred, and no StepFun physical request
was reserved or attempted. The expected original absent target
remained absent.

This is a **legitimate safety fail-closed response** to an
incomplete macOS entitlement profile, not evidence that Laya or
Hermes' Agent reasoning cannot work.

## 3. Independently checked rollback

The original orchestrator detected native_child_exit_code=1,
terminated its **four own** process groups (Laya runtime,
HTTP Observer, physical Provider budget proxy, native Hermes),
waited for verified shutdown and restored the isolated test Home
using the durable original checkpoint.

The independent incident verifier examined:
- the ORIGINAL private Hermes subprocess error (without exporting
  its path strings or raw output);
- original frozen SHA, unique H4B case and missing target;
- the post-run native SQLite archive: zero new H4B Session records;
- the H4B process provenance ledger: FOUR recorded original
  process groups, all NOT_RUNNING after cleanup;
- the original test Home online SQLite logical digest and restored
  OFF config / plugin state / plugin source;
- only stat-based independent auth.json metadata, UNCHANGED;
- original cumulative StepFun physical ledger SHA, UNCHANGED.

| Local/Provider outcome | Actual |
|---|---|
| Original H4B native Agent constructed | NO |
| Original H4B read_file call/result | NONE |
| Original H4B Retry/Completion Shadow | NONE |
| Original H4B StepFun physical requests | **0** |
| All H4B-owned process groups stopped | **4/4** |
| Test Home SQLite logical content restored | YES |
| Original plugin state/source and config restored | YES |
| Test Home ends in OFF | YES |
| Test auth.json metadata unchanged | YES |
| Production Hermes Gateway/process changed | NO |
| NAS Forgejo and GitHub main changed | NO |
| H1/H2/H3 original physical evidence changed | NO |

Global original StepFun physical requests remain **8/24**:
7 recorded real HTTP 200 and one H1 historical attempt whose
Provider outcome remains UNKNOWN. The nominal remaining budget
cannot be treated as free or automatically reusable.

The intentionally retained Git-ignored H4B original and
pre/post/recovery data are private research evidence, not a
modification to production Hermes. These files may be cleaned
only after separate explicit retention/verification decisions;
they must not be overwritten merely to make a test look successful.

## 4. Local fix after the original attempt, no re-execution

A subsequent source revision added only:
- one explicit OS Seatbelt write allow to the system null device
  /dev/null. This is a nonpersistent OS output sink; it does NOT
  permit arbitrary filesystem writes or remote network egress;
- a stronger offline preregistration test that actually invokes
  the REAL official run_oneshot preamble while replacing ONLY
  _run_agent with a synthetic zero-model/zero-Provider callable;
- matching checks in the H4B child-side --check-offline,
  so any future sandbox omission causes a pre-model block;
- an independent incident read-only verifier and adversarial
  tamper tests for missing/forged rollback, Provider and process
  evidence.

A disposable STRICTER-THAN-REAL macOS Seatbelt rehearsal
(all network DENIED, only temporary folder + /dev/null writable)
now successfully executes that official entry preamble with
NO main Agent/LLM request and verifies the original test Home's
SQLite/config/plugin/auth-stat state is unchanged. This proves
that the /dev/null admission problem is understood and corrected
in the later source, **not that a real failed-read task passed**.

The original H4B case MUST NOT be automatically rerun or overwritten.
If the evaluation continues, a separately pre-registered **H4C**
with distinct run ID, new isolated file/oracle, committed source
and a new one-shot rollback gate would be required. The four
already stopped H4B processes are not a reason to restart the
live production Gateway. Remaining StepFun request slots alone
do not authorize new tasks.

## 5. Evidence links and final disposition

- Original preregistration:
  PHASE8_3_REAL_H4B_REVERSIBLE_PREREGISTRATION.md
- Independent read-only incident verifier:
  scripts/phase8_3_verify_h4b_seatbelt_block.py
- Original privacy-safe machine-readable incident:
  results/processed/phase8_3_h4b_seatbelt_admission_blocked.json
- Full raw native logs, HMAC/test original and rollback baseline:
  retained only in Git-ignored owner-only private storage.

**H4B is BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION.**
Prior H1 real task PASS with global historical Provider issue,
H2 healthy Laya Shadow PASS_SCOPED and H3 Runtime-down fail-open
PASS_SCOPED remain unchanged. H4 original Gateway incident is
also unchanged. DSH D1–D4 live native E2E remain NOT RUN.
No Canary/Active, merged PR, production config mutation, or
paid retries were made by this incident/fix.
