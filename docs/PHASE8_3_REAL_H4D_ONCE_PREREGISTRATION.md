# Phase 8.3A H4D — one-shot real StepFun Plan trial, bounded and reversible

**Registered 2026-10-26 BEFORE the H4D real Provider experiment.**
This is a NEW case, not an overwrite or replay of H4, H4B or H4C.
The user explicitly approved the following capped real test after the
Phase 8.3A/C read-only gate: **ONLY StepFun Step Plan `step-5-preview`,
MAXIMUM 3 new physical upstream HTTPS requests in this H4D case,
MAXIMUM 90 seconds for one native Agent task; NO PAYG route, NO automatic
new Agent task/retry and NO Active/Canary**. These caps cannot be inferred
from the historical 24-global cap; the actual request operation is a
separate flag and may be launched ONCE only after all admission checks.

## Security and source

- Base branch is the finished PR #11 commit
  `da1761879ca2425306a78c4252a1604bc2ad820b`. This H4D code is in
  its own isolated worktree/branch, never written over any original H4
  incident, NAS Forgejo main, production Hermes/Gateway/DSH or other PR.
- Genuine Hermes uses the **pinned credential-free official Git archive**
  at source revision `4d04303818b61bf3aa09278af48356315515965b`,
  copied into a NEW ignored owner-only `private/phase8_3_native_real/
  h4d_hermes_archive`. Six original source hashes must pass the existing
  source verifier. Use the installed official venv Python for libraries,
  but NEVER import installed production Hermes source as the Agent code.
- Only the fixed pre-existing manually authenticated nonproduction
  `~/.hermes/system-one-phase83lab` may supply a Provider credential via
  Hermes's official auth store. Do not copy, print, export or back up
  `auth.json` bytes. The test Home must begin OFF and be independently
  validated with its single manual StepFun credential URL pinned to
  `http://127.0.0.1:18794`; no alternate provider or environment key.
  A private 0600/0700 durable checkpoint of TEST-ONLY SQLite, plugin
  state, plugin source and OFF config must be created BEFORE Shadow mode.
- The native child runs with real macOS Seatbelt, allowlisting ONLY its
  brand new missing-file scratch folder, test-Home known SQLite and one
  plugin state directory for writes. Explicit DENY auth/config, owner
  production home, unrelated Projects/H4 histories and all outbound
  network except the new isolated observer on localhost:18793 and
  capped physical Provider proxy on localhost:18794. Genuine Hermes tool
  registry exposes ONLY native `read_file`, and checks exact original
  preregistered absent filename. No write_file, shell tool, browser,
  file creation, alternate target or additional tool is allowed.
- Original StepFun HTTPS egress is exclusively the installed
  `phase8_2a_provider_cap.py` dedicated Plan-only upstream:
  `https://api.stepfun.com/step_plan/v1/chat/completions`, model
  `step-5-preview`. Hard-coded endpoint/model, port 18794, total 24 and
  case-specific per-run physical limit 3 are checked BEFORE service
  startup. The budget proxy checks authorization and appends a locked,
  fsynced reservation and `attempted` event BEFORE any HTTPS send, counts
  every main/auxiliary physical request, and fails closed when capped.
  Under no circumstances may an ordinary PAYG API/base URL be used.
- To retain one **GLOBAL** physical budget rather than silently inventing
  a reset 8/24 ledger, H4D's proxy may append H4D events ONLY to the
  unchanged historical owner-private ledger at the earlier Phase 8.3
  ignored directory. Pre-spend SHA-256 MUST exactly equal
  `5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`.
  The first 30 ORIGINAL H1/H2/H3 ledger rows must preserve that hash
  during all new reservations. Expected original reserved attempts H1=3,
  H2=3, H3=2, H4/H4B/H4C=0 and original H1 UNKNOWN=1. No new run may
  claim/relabel previous slots. Appending new actual physical request
  events is intentionally durable and **cannot be rolled back or unspent**.
  No test-Home, session or model rollback can undo a real API charge.

## Pre-run admission and stop conditions

1. Clean, exact frozen H4D commit; unit tests, safety tests, DSH build/
   typecheck/Vitest and public sanitizer pass. No private data or actual
   credential copied to Git. Existing PR #9/#10/#11 remain Draft.
2. H4D case/recovery/log/observer/private HMAC files have never existed.
   All three test loopback ports are free. Dedicated test Home OFF,
   plugin exactly matches public source, official auth status READY and
   entire manually pooled test credential route pinned to the proxy.
3. Full macOS Seatbelt deny probe passes before checkpoint. Create the
   durable test-only recovery checkpoint and exactly one new random
   **ABSENT** `h4d_absent_<24hex>.txt` manifest/prompt. Switch ONLY
   isolated test Home into Shadow.
4. Under the SAME actual kernel sandbox, execute official Hermes
   `run_oneshot` preamble and exact single read_file tool guard with
   synthetic NO-MODEL stub. If ANY startup/admission fails, STOP BEFORE
   enabling the real Provider proxy, restore test Home and report BLOCKED.
5. Start isolated warmed Laya/MLX runtime and HMAC HTTP Observer using
   H4D-owned, owner-only HOME/tmp/cache. Start one physically capped
   Step Plan proxy that MUST initially report 8 global / 0 H4D usage.
   Only then execute ONE genuine native Hermes Agent turn with no extra
   tool/autoretry. Native turn is limited to 90 seconds. Stop all owned
   process groups by recorded PID/PGID/UID/kernel-start-time. Bounded
   outstanding request drain may not create new tasks/attempts and must
   remain inside the one-trial 90-second native/request observation period.
6. Archive actual post-run SQLite and plugin evidence in a separate 0600
   H4D-owned recovery folder, restore original OFF SQLite/config/plugin
   state, verify auth file metadata unchanged, no original/production
   files altered, and ports unused. On unsafe process ownership never
   blindly kill by name or restore underneath a running process: report
   BLOCKED and require user manual inspection.

## Independent acceptance

- True native H4D AIAgent Session, one read_file call with the PRE-AGENT
  exact manifest path, one same-ID tool result with structured
  `not_found=true` / original `File not found` error, no target mutation,
  no other tool and normal native Session closure. Agent final words are
  not enough to prove the actual tool or independent decision gold.
- Two real local Laya/MLX Completion HTTP 200 observations and one
  advisory-only Retry HTTP observation bound to the actual native
  SQLite Session/Turn/Tool via independent keyed HMAC correlation.
  A Retry safety guard may return `ask_user` rule-only when its real retry
  budget is unverified: do NOT invent local Retry model inference.
- Between 1 and 3 physical Step Plan Provider attempts, no H4D attempt
  outside slots 9–11, actual terminal outcomes independently recorded;
  H1's original UNKNOWN remains UNKNOWN and real subscription usage /
  credit debit remains UNKNOWN until supported billing evidence exists.
- Independent read-only H4D adjudication must run in a separate process
  against committed exact source and archived post-run records. Original
  orchestrator returncode is never sufficient to label PASS. Any nonzero
  native exit, missing/error tool evidence, unknown new Provider result,
  missing correlation or failed rollback => PARTIAL/BLOCKED, not an
  invented model success. Not a statistical model-value experiment.

**No Active/Canary permission. No automatic merge. No expanding the
approved 3-physical/90s/Step-Plan-only limits, even when a failure occurs.**
