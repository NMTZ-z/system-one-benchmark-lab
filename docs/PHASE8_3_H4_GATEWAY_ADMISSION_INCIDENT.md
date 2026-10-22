# Phase 8.3A — H4 real-run attempt blocked before native Agent startup

**2026-10-22. Verified evidence classification: BLOCKED_BEFORE_NATIVE_AGENT_AND_PROVIDER.**
**Original H4 source: a32eb078593cb4a9139c9aa181d017b9bb010298.**
**This is NOT a native read_file failure result, NOT a Retry Shadow E2E
result and NOT a completed StepFun H4 main-model experiment.**

## Incident and actual extent of execution

The H4 candidate was preregistered, committed and published on its
isolated PR branch. It had passed 1231/1231 Python regression tests,
64/64 DSH tests, TypeScript typecheck/build and a clean 289-file
public privacy sanitizer. The only designated test Home was
~/.hermes/system-one-phase83lab, using the previously manually
authenticated Plan credential pinned to local 127.0.0.1:18794.
It was switched from OFF to Shadow only for this candidate.

The one-shot H4 orchestration script did start its own LOCAL services:
the pinned Laya/MLX server, the correlation observer and the physical
Provider request-budget proxy, on 18782/18793/18794. It then
attempted to start Hermes' native -z one-shot read_missing task.
The currently installed Hermes CLI routes one-shot traffic through
a host-owned multiplexing Gateway first. The host already had a live
Gateway started by profile default. The fresh isolated System One
test Home was not served by that Gateway. The Gateway startup path
refused a second instance, before any actual main Provider call
or native Agent tool execution.

We did NOT restart, replace, attach credentials to, reconfigure or
force-start the production Gateway or its existing profiles.

The private original H4 candidate created only the brand-new
disposable missing target's manifest and the original failure log.
The target itself was never created. The Hermes child exited with
process_exit_code **1**, no usage JSON, no Agent stdout, no native
SQLite Session, no true tool-result messages and no real H4
observer HTTP records.

The pre-existing native runner wrapper itself had a safety defect:
it reported the underlying child process_exit_code=1 in its
private JSON but exited with shell returncode 0, which the outer
H4 orchestrator initially recorded as native_agent_exit_code=0.
Despite that, the H4 scoped acceptance remained
PARTIAL_OR_BLOCKED because there was no native oracle, no
Completion/Retry observation and no physical Provider attempt.
This incident also proves why a native Agent's explicit exit code
must be reconciled independently of a wrapper's status.

The wrapper has been corrected **after the original frozen H4
execution**: any actual subprocess failure, unknown exit or
timeout now returns nonzero to its caller. New tests include
a genuine Agent success, various failed statuses, timeout,
missing result and boolean/string codes so the original mistake
cannot be silently accepted again.

## Original Provider history and isolation

| Physical StepFun reservation | H1 OFF | H2 healthy Shadow | H3 Runtime-down | H4 startup attempt |
|---|---:|---:|---:|---:|
| Reserved | 3 | 3 | 2 | **0** |
| Attempted | 3 | 3 | 2 | **0** |
| Genuine HTTP 200 | 2 | 3 | 2 | **0** |
| Unknown/unfinalized | 1 | 0 | 0 | **0** |

Total existing physical Provider requests: **8/24**.
The SHA-256 of the actual global request ledger was checked after
the H4 attempt and remains:

5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb

The original H1 slot 1 remains unknown and unfixed. No new StepFun
request was observed by the outbound cap, and H4 itself cannot have
incurred a new main-model Provider charge through that cap.
Actual lifetime subscription billing remains unmeasured.

All locally started H4 test-only services were terminated by the
orchestrator. The isolated test Home returned to OFF. The public
GitHub main, NAS Forgejo main and production Hermes Home remain
unchanged. No attempt was made to circumvent the host-wide
single Gateway restriction.

## Gateway-independent native path: SOURCE-ONLY finding

Read-only inspection of the current official installed Hermes
source found that top-level CLI -z delegates to the gateway chat
launcher. In contrast, the installed native Python module
hermes_cli.oneshot still exports run_oneshot, which builds an
in-process genuine AIAgent using the owner's official implementation,
without a connect_gateway call in that function.

This alternative was checked **by import and source inspection only,
with no prompt submitted and zero main Provider requests**.
The current preflight records the two installed-source SHA-256
digests, signature availability, and separate distinction between
the gateway-backed CLI and direct AIAgent construction. This
does not prove a full direct one-shot run, actual tool outcome
or compatibility with the current test Home/Adapter/hard budget.

A subsequent H4B is only a *candidate* for a separate controlled,
preregistered one-shot experiment using that official in-process
entry. It must have a NEW case ID, NEW nonce/target, strict clean
Git source, and the original shared physical budget unchanged.
This incident's private H4 files must never be deleted, reused
or overwritten to enable another run. Additional real execution
is NOT automatically approved by this incident or by remaining
budget slots.

## Independently reproducible evidence

- Read-only source: scripts/phase8_3_verify_h4_gateway_block.py.
- Privacy-safe aggregate:
  results/processed/phase8_3_h4_gateway_admission_blocked.json.
- Gateway-independent source-only probe:
  scripts/phase8_3_hermes_direct_entry_preflight.py.
- Original stderr, logs, manifest and per-process results remain
  only under ignored restricted private/phase8_3_native_real/.
- The exact original H4 execution SHA remains a32eb07; all later
  fixes use separate commits and do NOT upgrade this case's verdict.

The verifier requires matching original source/run/case, the
underlying Hermes nonzero exit, missing native SQLite Session,
unchanged global Provider SHA and zero H4 physical attempts.
It refuses to turn this gateway-startup failure into a
native file failure or Retry Gate PASS.

## Decision

H4 one-shot real failed-read Agent and Retry/Completion E2E
**NOT RUN / BLOCKED before native Agent**.

H1 remains scoped native PASS but historical Provider terminal
BLOCKED; H2 healthy Shadow and H3 Runtime-down are scoped PASS.
DSH D1–D4 real native tasks remain NOT RUN pending separately
authorized credential input and frozen native E2E runner.
No Active/Canary authority was introduced, no merge authorized.
Do not rerun H4 automatically and do not restart production Gateway.
