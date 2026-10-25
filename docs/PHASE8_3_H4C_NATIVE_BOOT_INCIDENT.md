# Phase 8.3A H4C: isolated true Hermes one-shot startup blocked, rollback verified

**Executed 2026-10-23. Original frozen source:**
8776de71a88821dffd84bfd4976927fd0cfe9c3a.

**Final scoped result: BLOCKED_BEFORE_NATIVE_SESSION_AND_PROVIDER.**
This is NOT a completed real native missing-file error, NOT a
Retry Shadow PASS and NOT a failed Laya decision.

## 1. Separate case, exact provenance

The original H4 was blocked by an occupied host Gateway.
The subsequent H4B was blocked by macOS Seatbelt denying the
one-shot's write to /dev/null. Both prior one-shot attempts had
ZERO physical Provider calls. Their source commits, private
original logs and rollback receipts remain unchanged.

H4C was distinctly preregistered after inspecting and addressing
these earlier blockers. Its H4C-only directories were unused
before the candidate was frozen and published on the Draft PR.
The exact original source was 8776de7 and had passed:

- Full Python regression **1338/1338 PASS**.
- DSH Vitest **64/64 PASS** and TypeScript typecheck/build PASS.
- Privacy-safe public release **321 files, publish_ready=true**.
- Clean Git and strict manual-test credential/Provider route check.
- Independent H4B historical original rollback verification.
- Seatbelt file/port restrictions and isolated Home read/write
  admission checks.
- Official Hermes run_oneshot stdout/stderr preamble executed
  using a synthetic, zero-network _run_agent stub with all
  network DENIED, and exact test Home baseline digests unchanged.
- Cumulative Provider ledger SHA-256 integrity **8/24**.

One real H4C was then started with the official Hermes
in-process one-shot behind the pinned macOS Seatbelt and
locally budgeted StepFun outbound service. The test-only
Laya/MLX, HMAC Observer and physical-cap proxy were
created as new, separately recorded process groups, with
H4C-local ancillary HOME/tmp/cache directories. No production
Gateway was started, restarted or reconfigured.

## 2. Actual failure, bounded scope

The genuine native Hermes child returned exit code **1**.
Its private official one-shot usage file reported:
- failed=true;
- failure class exactly SystemExit(1);
- no main-model API call record.

The original Hermes one-shot suppresses stdout/stderr
internally during the _run_agent execution path, so the
underlying SystemExit(1) source is NOT independently known.
There was **no new H4C SQLite Session**, no native
read_file call/result, no Completion/Retry HTTP observation,
and no StepFun Provider request recorded by the hard-cap
proxy. The missing-file test target still did not exist.

This evidence does NOT prove the cause is the API credential,
Seatbelt, provider routing, plugins, MCP startup or AIAgent
initialization. It only proves that the official child aborted
before a persistent native Session or external Provider call.

Do not infer an underlying error from missing stderr or
automatically open additional paid experiments to debug it.

## 3. Independent recovery and zero permanent production impact

The H4C orchestrator did not retry the failed child.
The original bounded cleanup performed:
- termination and safe exit verification of all **4/4** new
  H4C-owned process groups, using PID/PGID/UID/start-time;
- successful durable archiving of original postrun SQLite
  and plugin state evidence under *h4c_recovery*;
- full rollback of isolated test Home original SQLite logical
  state, plugin JSON/source/locks and exact OFF config;
- original isolated auth.json stat-only metadata unchanged;
- no test-only listener left on local 18782/18793/18794;
- no modification to production Hermes, host Gateway, NAS
  Forgejo main or GitHub main;
- no overwrite of H4B original recovery snapshots, H4 original
  Gateway incident or historical H1–H3 evidence.

The original cumulative Provider ledger digest stayed:

5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb

The count remains **8/24 attempted physical requests**:
H1 3 (2 recorded HTTP 200 and 1 UNKNOWN),
H2 3 recorded HTTP 200, H3 2 recorded HTTP 200,
H4 0, H4B 0, H4C 0. Actual historical StepFun Plan
credit debits are still unknown.

This is an actual successful TEST-ONLY recovery, not a
guarantee that every possible OS crash or external API
side effect is reversible. Original private research files
and backups remain Git-ignored and may be retained for audit,
but they never replaced production files.

## 4. Independent postrun result and next engineering action

Read-only evidence checker:

scripts/phase8_3_verify_h4c_preactive_block.py

Public allowlisted aggregate:

results/processed/phase8_3_h4c_preactive_native_blocked.json

It checks the original frozen SHA, actual child usage
SystemExit(1), zero new native SQLite Session, original
missing target absence, no observer events, zero new
Provider reservations/attempts, 4 original terminated
process groups, original SQLite/plugin/config restored
and unchanged auth metadata, and unchanged prior H4B
recovery. No raw prompt, key, private path, Session ID
or tool bytes are committed to Git.

**Engineering stop decision:** H4C is a single one-shot
blocked before real native task observation. Its original
private evidence must not be overwritten or rerun.
Future investigation should first instrument the official
Hermes _run_agent initialization stages using a
STRICTLY ZERO-NETWORK / ZERO-PAID local simulation in
another isolated disposable test profile, with its own
full rollback. A stage-level error can then be identified
without creating H4D/H4E paid trials or loosening Seatbelt.

A separate new genuine Provider-backed case should be
considered ONLY after that full native initialization
simulation passes and a new clean preregistration is
reviewed. This report itself grants no new Provider or
Active/Canary authorization.

H1/8.3A global physical Provider integrity remains BLOCKED
by the original one unresolved H1 slot even when H2 and H3
show scoped PASS. No real Agent-level cost/time savings
have been independently established.
