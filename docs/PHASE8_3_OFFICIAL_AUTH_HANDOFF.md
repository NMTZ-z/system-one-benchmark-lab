# Phase 8.3A — Fresh isolated test authentication handoff

**2026-10-21 — Offline setup PASS; new credential NOT PROVISIONED;
real Provider E2E NOT RUN.**

The former attempt to attach an older test credential to a fresh test
environment was blocked. That boundary has not been bypassed: no legacy or
production credential was copied, linked, exported or reused.

## New environments, created without credentials

Hermes now has a separate, empty OFF-only test home at:

    private/phase8_3_native_real/hermes_home/

It contains only publicly committed Hermes plugin source and safe test
configuration. The main provider is StepFun Step Plan step-5-preview, and
its URL is locked to the capped localhost port 18794, never an uncapped
Provider or pay-as-you-go endpoint.

Two new DSH SDK patches (OFF and Shadow) exist under:

    private/phase8_3_native_real/dsh_patches/

They use the same capped localhost Provider route, no automatic retry,
OFF/Shadow-only Gate settings and an environment-variable *name* for
secure input. There is no embedded token or other credential.

Both official DSH SDK configurations were independently tested with only
initialize and shutdown RPC, under a clean HOME/DSH_HOME and with NO
credential variables inherited. Both initialized successfully and shut
down normally: native tasks 0, paid main-model requests 0.

The new test files are Git-ignored, private-permission protected, and
the scaffolder rejects suspicious credential symlinks (even dangling
ones), unsafe Provider URLs, Active/Canary or profile overwriting.

## The one required user-controlled Hermes login

A user may authenticate this NEW, dedicated test profile using Hermes'
official interactive terminal prompt. On the user's Mac, from a trusted
interactive Terminal window:

~~~bash
cd ~/Projects/system-one-phase8-3
export HERMES_HOME="$PWD/private/phase8_3_native_real/hermes_home"
export HERMES_DISABLE_LAZY_INSTALLS=1
# Use a fresh terminal and do not inherit existing provider-token/route overrides.
unset STEPFUN_API_KEY STEPFUN_BASE_URL

# The API key is entered ONLY at the official non-echoing prompt.
# Never use the --api-key argument or paste any key into ChatGPT.
hermes auth add stepfun --type api-key --label phase8-3-isolated

# Read-only official authentication and loopback-route preflight.
python3.12 scripts/phase8_3_prepare_clean_home.py --check
~~~

The read-only check must report credential_status READY,
credential_stage_ready true and worktree_clean true. Any other value
means BLOCKED. Its separate ready_for_provider_test field deliberately
remains FALSE until a later frozen native runner proves a live, hard-capped
Provider outlet. Authentication alone can never approve or trigger a
Provider request, Active control or an uncapped run. The auth status preflight additionally runs with an allowlisted clean
HOME/HERMES_HOME environment, excluding any inherited provider keys or
proxy overrides. No existing or production credentials should be linked
to the new profile.

DeepSeek Harness separately requires an owner-supplied
STEPFUN_API_KEY environment variable in an isolated real-run process.
That credential has NOT been acquired or imported and must not be
extracted from Hermes. The real DSH native test is therefore BLOCKED
until a supported separate secure-input mechanism is available.

## Repeat the no-Provider native SDK check

~~~bash
cd ~/Projects/system-one-phase8-3
python3.12 scripts/phase8_3_sdk_offline_preflight.py --run
~~~

The SDK tool permits ONLY initialize and shutdown, and sets a fresh
environment that cannot inherit StepFun/other Provider keys or proxy
variables. It sends zero prompts, native tool tasks or Provider calls.

## Real test authorization remains tightly bounded

Before a future real request, source must be frozen and clean; provider
egress must be proved restricted to the existing StepFun Step Plan
request-cap proxy, with 24 maximum physical requests globally and 3 per
native scenario, including auxiliaries and failed calls. Each native
task has a 90-second wall limit. The only local decision Runtime is
the separately isolated Laya/MLX service, never Active.

The eight preregistered Hermes and DSH tests must use independently
checked native tool/file results, opt-in HMAC request-ID correlation
and independent budget reconciliation. Provider credit consumption
remains unknown unless separately verified. No new paid API Provider,
purchase, production state mutation, or Git merge is allowed.

## Current evidence status

| Item | Verdict |
|---|---|
| Hermes empty isolated OFF profile | PASS |
| DSH OFF/Shadow official native SDK init/shutdown | PASS, no Provider |
| Private auth file for new Hermes home | NOT PRESENT |
| Separate DSH secure Provider credential | NOT PROVISIONED |
| Eight-case StepFun + Laya native Shadow E2E | BLOCKED, NOT RUN |
| Real Agent value or billed savings | NOT MEASURED |
| Active readiness | NOT AUTHORIZED |

This document intentionally never contains any credential value,
original user file path, raw SDK frame, native Session ID, or private
task data.


## Switch only the fresh test home OFF/Shadow

After separate official login and the real budget preflight, a future
bounded native runner may select the appropriate test mode using:

~~~bash
cd ~/Projects/system-one-phase8-3
python3.12 scripts/phase8_3_prepare_clean_home.py --set-mode shadow
# or explicitly restore the harmless baseline:
python3.12 scripts/phase8_3_prepare_clean_home.py --set-mode off
~~~

This command edits ONLY the new ignored Hermes test-home config using
an atomic file replacement, refuses Active or Canary, and never reads or
changes production configuration. The real Provider experiment remains
BLOCKED until the separate authentication and budget gates pass.


## New-profile regression and exact readiness status

The final new-profile / SDK hardening regression on 2026-10-21 passed:

- Python full tree: 1030/1030 PASS.
- DSH Vitest: 64/64 PASS.
- TypeScript typecheck and DSH build: PASS.
- SDK native bootstrap: OFF and Shadow initialize/shutdown PASS with
  no Provider credential in subprocess environment, zero submitted tasks.
- Fresh Hermes status: credential_status MISSING_NEW_PROFILE_LOGIN;
  credential_stage_ready false, ready_for_provider_test false,
  live_provider_budget_attested false.
- Test Home contains no auth.json, symlinked credential or token file;
  none of the previous test/prod credentials were transferred.

These checks confirm that the **local setup is prepared**, not that real
native Provider E2E is authorized, functional or billable within a
known amount. No extra real StepFun call was attempted.
