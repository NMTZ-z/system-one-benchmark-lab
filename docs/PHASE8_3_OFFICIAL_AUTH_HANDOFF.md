# Phase 8.3A — Supported isolated Hermes authentication

**Updated 2026-10-21: dependency root cause diagnosed, supported
shared-dependency test Home prepared. Real StepFun E2E NOT RUN.**

## What caused the reported error

The first test Home, under this repository's ignored private/ directory,
was deliberately independent of the main Hermes Home. Recent Hermes PM
scopes its committed Python environment to HERMES_HOME. The normal owner's
dependency generation exists under ~/.hermes/installs/, while the
repository-private Home lacked its own committed generation.

Hermes therefore refused authentication before showing the credential
prompt and suggested hermes pm repair. This did not indicate a failed
StepFun token, an unavailable model or a System One Runtime problem.

An official, scoped PM repair was attempted only inside the empty test
Home. It entered uv dependency installation but reached the bounded
execution timeout before a generation was committed. The abandoned
test-only install/cache directories and incomplete marker were subsequently
cleaned up. No production dependency state or default Profile was
modified. **Do not rerun PM repair using the former repository-private
test Home.**

## Supported recovery without copying credentials

The Hermes source also supports independent data Homes located *under*
the owner's existing ~/.hermes/ root: those reuse the already committed
dependency environment. A fixed new test-only Home was created at:

    ~/.hermes/system-one-phase83lab

It is deliberately NOT under ~/.hermes/profiles/, so it is not a named
Profile automatically enumerated by a running Hermes multiplexer.
Its config, intentionally empty .env, authentication state and plugin
directory remain dedicated to the test. The original default Home and
gateway configuration are unchanged.

The new Home was initialized without cloning or linking any previous
credential. It contains only the required source plugin files and the
explicit OFF-only StepFun Step Plan configuration. The model Provider
address is fixed to http://127.0.0.1:18794 (the planned controlled
network-outlet proxy), **not** the pay-as-you-go API. Its auth.json file
is not yet present.

Verified in the actual Hermes CLI with this Home:
- Existing owner dependency environment available: YES.
- Official Hermes auth status: stepfun: logged out.
- No PM dependency error at startup.
- New private credential imported: NO.
- Real main-model requests: 0.
- Existing production config and committed dependency record untouched.

This is an *authentication preflight* only; no native Agent test was run.

## Required next human-controlled action on Mac

Run these commands from a Mac Terminal in a new shell. Enter the StepFun
key **only** at the official secure interactive prompt. Do not put it in
CLI arguments, this conversation, project code or shell history.

~~~bash
cd ~/Projects/system-one-phase8-3
export HERMES_HOME="$HOME/.hermes/system-one-phase83lab"
export HERMES_DISABLE_LAZY_INSTALLS=1
unset STEPFUN_API_KEY STEPFUN_BASE_URL

hermes auth add stepfun --type api-key --label phase8-3-isolated

../system-one-benchmark-lab/.venv/bin/python \
  scripts/phase8_3_prepare_shared_dependency_home.py --check
~~~

Do not use the former Home at
private/phase8_3_native_real/hermes_home for this login.
Do not run hermes pm repair against the normal owner Profile. The
official CLI for the fresh Home already launches.

The check must eventually return credential_status READY and
credential_stage_ready true. All other values mean authentication
is incomplete or the controlled proxy route was not authenticated.
Even when credentials are ready, the real Provider test is **still
BLOCKED** until a separately frozen native runner verifies the
24-request global / 3-request per-task physical cap, isolated model
routing, evidence collectors and native task limits.

This check intentionally does not send any StepFun model request and
does not grant Active/Canary rights.

## DeepSeek Harness isolation

The new OFF/Shadow DSH SDK patch files under
private/phase8_3_native_real/dsh_patches/ remain unchanged. Both modes
have passed true native SDK initialize/shutdown with an empty Provider
environment and 0 model calls. They are *not* a real Provider E2E test.

The DSH main-Provider adapter requires a separate secure process-scoped
StepFun credential. This tool chain must not extract or copy a key from
the new Hermes Home, earlier test Homes, the owner's default Home, .env
or another agent. This remains independently BLOCKED.

## Status and safety gates

| Dimension | Verdict |
|---|---|
| Official Hermes dependency-state root cause | VERIFIED |
| Owner Python dependencies changed | NO |
| Fixed standalone test Home under owner data root | PASS |
| Hermes auth CLI bootstrap using that Home | PASS, logged out |
| Old key/token imported or symlinked | NO |
| DSH SDK OFF/Shadow initialization | PASS, no Provider |
| Actual StepFun requests in this qualification round | 0 |
| Hermes new-home interactive login | USER ACTION STILL REQUIRED |
| Native Hermes + DSH eight-task real E2E | BLOCKED, NOT RUN |
| Agent API/token/time/billing savings | NOT MEASURED |
| System One Active authorization | NOT AUTHORIZED |

Only privacy-safe configuration/source state and bounded derived evidence
may be committed. Raw keys, sessions, request/response content and local
test files never enter public Git. The Phase 8.3 PR stays Draft.


## Native real-run boundary on this fixed Home

The existing Phase 8.2A native runner has now been narrowly extended to
accept only the *exact* new shared-dependency test Home as an additional
authorized identity. Other Homes still require its original strict
repository-private validation. The new Home is independently checked
by the Phase 8.3 official auth tool before any Provider I/O.

For the new Home only, the runner now:
- Requires official clean-environment login verification, not merely an
  inherited STEPFUN_API_KEY or a credential in another Home.
- Pins StepFun egress to local port 18794 and checks that the live
  budget outlet declares no more than 24 total and exactly 3 per run.
- Permits only OFF/Shadow, bounded read-only native tasks and at most
  90 seconds per task; it rejects file writes, model-control changes,
  unexpected Provider ports, wider budgets and Active/Canary.
- Drops inherited Provider keys from the native subprocess, while
  allowing a separately supplied 32-byte test-only HMAC evidence key
  after validating its encoding. It never retrieves a Provider token.
- Still requires a clean frozen Git SHA, an opted-in existing Step Plan
  test, exact isolated plugin bytes and a healthy scoped budget proxy.

This is code-path preparation, NOT an authorization to start a real
request. The complete eight-case matrix, including missing-file
failure scenarios and independent per-task provenance, requires
separately audited runner and orchestration steps before execution.
The DSH Provider credential remains independently unprovisioned.


## Offline regression after shared-dependency fix

The final isolated authentication and native-run extension passed a
complete Python regression **1051/1051**, DSH Vitest **64/64**,
TypeScript typecheck PASS and DSH build PASS (2026-10-21).

The dedicated shared-dependency Home still has **no auth.json** and
Hermes officially reports stepfun: logged out. This proves that
the CLI bootstrap now succeeds without loading any legacy credentials,
NOT that a live StepFun task was authorized or run.
