# Phase 8.3A — Native StepFun + Laya Shadow real-provider attempt

**Current verdict: BLOCKED BEFORE PROVIDER EXECUTION.**
**Execution environment: isolated Phase 8.3 worktree, 2026-10-21.**

This report distinguishes an **authorized plan** from an actually executed
real-provider validation. Do not interpret existing 8.2A real evidence, 8.2B
Mock evidence or the new Phase 8.3 synthetic offline accuracy as success of
this 8.3A real post-change test.

## 1. Established baselines

- GitHub main: 062d52e753e7e00d91a536dc81e9d85b8819cb12.
- Phase 8.3 Draft PR #9; dedicated clean feature worktree, unchanged
  production and NAS main.
- Predeclared test protocol source commit before any external request:
  5dfc5b6add32eeb37bd8a8488485f77d529e4758.
- Existing StepFun Step Plan test-profile read-only authentication status
  reported logged in. This is only an **auth metadata observation**:
  not proof of request routing, spend, credit balance or successful
  current main-model inference.
- No existing production Gateway, Agent Home or unrelated loopback Runtime
  was reconfigured, restarted or altered.
- The private test environment for this experiment **was not created**:
  an attempted operation to connect existing isolated credentials to a
  fresh isolated native test setup was rejected by the available tool's
  external safety check. The operation did not execute; a subsequent
  read-only file check confirmed the new Phase 8.3 private test directory
  did not exist.

## 2. What was not done

The tool safety block was respected. We did **not** retry credential
access using an alternate route, link/copy any token, inspect or print a
secret, move to production authentication, use a secondary Provider, or
bypass the capped egress plan.

No Phase 8.3 native tool tasks were launched. No StepFun Step Plan proxy
listener, new provider budget ledger, private Session stream or fresh
native event / HTTP trace was created. Therefore there is **no measured
Provider attempt denominator** for new native sessions. The observed
number of *new experiment initiated requests* is 0, but this is
**not a statement about the user's total subscription usage**.

Per-scenario status, all **BLOCKED / NOT RUN**:

| Test | Native platform | Test state | Real native evidence |
|---|---|---|---|
| H1 | Hermes OFF read | NOT RUN | none |
| H2 | Hermes Shadow healthy | NOT RUN | none |
| H3 | Hermes Shadow Runtime down | NOT RUN | none |
| H4 | Hermes Shadow failed read | NOT RUN | none |
| D1 | DSH SDK OFF read | NOT RUN | none |
| D2 | DSH SDK Shadow healthy | NOT RUN | none |
| D3 | DSH SDK Shadow Runtime down | NOT RUN | none |
| D4 | DSH SDK Shadow failed read | NOT RUN | none |

**Do not claim 8.2B exact native-to-HTTP correlation on a fresh real StepFun
execution, real Provider token spend, real Agent overhead or savings.**

## 3. Evidence obtained without credentials

Existing bounded test components were reviewed and reused without
reimplementation:
- Phase 8.2A atomic Provider reservation and request ledger, including
  proper fail-closed behavior for exhausted/corrupted budgets.
- Phase 8.2B independent HMAC native/Adapter/HTTP correlation validator,
  including no PASS from clock proximity alone.
- Phase 8.2B metadata-only Evidence Contract and offline synthetic verifier.
- Phase 8.3 preregistered Shadow matrix and previous new synthetic holdout.

The supplemental offline regression under
tests/test_phase8_3_native_real_budget_preflight.py checks 8 runs ×
3 physical request slots = 24 maximum across one durable ledger,
nonrefundable failed/unknown requests, corruption refusal, missing
native event provenance, and lack of false task PASS when no Agent ran.
These are **unit/contract tests, NOT real main-model calls or native E2E**.

## 4. Scope of next permissible action

Real tests remain **BLOCKED** until the owner/environment establishes a
supported, independently authorized and bounded isolated authentication
path that passes the tool safety boundary. Do not resolve the block by
linking/copying old credentials, reading a production secret or routing
around permission checks.

When properly available, retain the frozen test plan:
only the existing StepFun Plan endpoint, total physical cap 24,
per-run cap 3 and <=90 s per native task, real Laya/MLX Shadow,
independent native file oracle, HMAC exact correlation, no Active.
Stop and separately report any unmatched native results or
Provider count, unknown usage or budget mismatch.

**Final offline verification (2026-10-21):**
Python test suite **1012/1012 PASS**; DSH Vitest **64/64 PASS**,
TypeScript typecheck **PASS**, TypeScript build **PASS**. The focused
new/legacy provider budget and 8.2B causal-correlation regression
completed **28/28 PASS**. No paid Provider calls were made by these
offline tests; their Mock HTTP servers were loopback-only.

**Engineering offline evidence:** PASS within non-Provider scope.
**Native Real Provider Validation:** BLOCKED.
**Model incremental real-Agent value:** NOT_ESTABLISHED.
**Actual savings:** NOT_MEASURED.
**Active readiness:** NOT_AUTHORIZED.


## 5. Clean empty profiles and offline SDK initialization (2026-10-21)

Following the previous safety block on legacy credential linkage, we
created a NEW Hermes OFF-only test profile and two DSH OFF/Shadow SDK
configurations using scripts/phase8_3_prepare_clean_home.py. Only safe
source-controlled plugin bytes and explicit loopback test settings were
written; no legacy/production auth file, key or token was copied or linked.

With zero credential environment variables and no Agent task submitted,
the official native DSH SDK completed initialize and shutdown in both
OFF and Shadow modes, with process exit code 0. The repeatable
scripts/phase8_3_sdk_offline_preflight.py reproduces this no-Provider
test and outputs only allowlisted status fields.

The Hermes test home remains credential-empty and in OFF mode, so
real StepFun Provider requests and native Agent task acceptance remain
BLOCKED. The earlier credential restriction was not bypassed.

See the official operator handoff PHASE8_3_OFFICIAL_AUTH_HANDOFF.md
for the separate, supported interactive authentication path.


## 6. Credential-stage exact check and regression (2026-10-21)

The fresh Hermes OFF Home and DSH OFF/Shadow SDK patches were audited again.
The strict official auth preflight uses an **allowlisted clean environment**
that drops inherited STEPFUN/other Provider tokens, route overrides and
production HOME fallbacks. It returned MISSING_NEW_PROFILE_LOGIN, with
credential_stage_ready false and live_provider_budget_attested false.
The new test auth.json still does not exist.

Both DSH SDK modes requalified cleanly with no key in the subprocess
environment, initialize/shutdown only. No provider call, Session prompt
or native tool action occurred.

Python 1030/1030 PASS, DSH Vitest 64/64 PASS, TypeScript typecheck and
build PASS. New symlink, mode, route, inherited-token and byte-identity
regressions pass.

**Native Real Provider E2E is still BLOCKED.** The only supported next
step is for the owner to use the official fresh test-home interactive
auth login described in PHASE8_3_OFFICIAL_AUTH_HANDOFF.md. The prior
tool safety block has not been bypassed.
