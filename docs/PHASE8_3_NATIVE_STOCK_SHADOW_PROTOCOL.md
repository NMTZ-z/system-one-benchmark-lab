# Phase 8.3A supplement: Stock Hermes native-to-Shadow closure protocol

**Status: preregistration. Do not report an outcome until this source and
protocol are committed and the clean frozen code is executed.**

## Question and precommitted experiment

Does a genuine Hermes `read_file` failure, with its **unmodified** upstream
`LocalEnvironment` shell snapshot and `ShellFileOperations._exec`, reach
System One's Completion and Retry Shadow observers with exact native
SQLite-to-hook-to-HTTP causal linkage? Does local pinned Laya actually
participate when eligible? Does the *same* actual native task still complete
under a failing Runtime, without System One retrying tools or changing the
native Agent? This is a **technical feasibility/control study**, not a real
main-model decision-quality or savings experiment.

Use a frozen credential-free Hermes Git archive at
`4d04303818b61bf3aa09278af48356315515965b`, verified against six
original upstream SHA-256 values already committed in
`STOCK_SOURCE_SHA256`. Main-model transport is a **strictly synthetic**
`httpx.MockTransport` fixture (one tool-call response, then one final
response *after* consuming the real missing-file tool error). This
simulation exercises the official Hermes AIAgent, tool executor, lifecycle
hooks, SQLite and unchanged System One Hermes Adapter. It does **not**
represent StepFun behavior or billed Token usage.

Predeclare four separate new cases, in this order:

| Case | Hermes mode | System One runtime | Expected observations | Actual local model |
|---|---|---|---|---|
| `off_stock_shell` | OFF | no runtime | 0 HTTP / 0 Adapter | 0 |
| `shadow_stock_fixture` | Shadow | deterministic fixture | 3 correlated HTTP 200 | 0 real Laya; two fixture predictions |
| `shadow_stock_mlx` | Shadow | pinned Laya on local MLX | 3 correlated HTTP 200 | 2 actual Completion predictions + separate warmup |
| `shadow_stock_503` | Shadow | controlled HTTP 503 | 3 HTTP 503, 3 failed-open events | 0 |

The historical four-case matrix remains unchanged and is not silently
regenerated. Every case gets a new disposable scratch tree and a fresh
absent-file target, not an original H4/H4B/H4C path. Frozen Laya revision:
`f9ab0b228f0fc0f14d873dbc99038f135c2da1b2` with local weights SHA-256
`4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e`.
No download, installation into owner environments or alternative model.

## Safety, authority and true acceptance criteria

- **Mac Seatbelt denies external network** (only the per-case owned local
  Runtime port is allowed for Shadow). Sandbox denies read/write access to
  production user data and writes outside new disposable HOME/scratch.
  Admission must demonstrate real forbidden read/write/network denial.
- Only these explicitly enumerated stock cases may use `process-fork` in
  their disposable *native* child. The child audit admits only upstream
  Bash and a bounded set of upstream environment helper subprocesses in
  disposable cwd, while recording structured/limited process witnesses.
  Existing old four cases retain their no-fork policies.
- No production Gateway, existing authenticated profiles, NAS Forgejo
  `main`, GitHub `main`, original private evidence or model cache content
  may be changed. Child process owners are verified by PID/PGID/UID/start
  time, stopped, and their disposable SQLite state is restored/checked.
- Every case must exhibit **exactly one** authentic missing-file
  `read_file` invocation, matching tool call/result ID and original
  `not_found=true` and `File not found:` status; no file creation, no
  second tool call and no extra main Provider fixture response.
- Three stock Bash startup/tool execution witnesses, at least one login
  and two nonlogin, no mock directory listing, no unapproved subprocess.
  All original shell/file source file digests must match.
- In Shadow, verify exactly two Completion and one Retry observation
  through native Session/Turn/Tool IDs, keyed HMAC and matching HTTP
  request/decision references; never match by timing or final Agent prose.
  Under 503, every observer must fail open with unchanged native result.
- Expected Retry decision here is **`ask_user` by deterministic rule,
  reason `retry_budget_unverified`**. Zero actual Retry model inference is
  correct; a model or Agent may not grant a retry budget or infer a write
  did not apply. Observed local Laya involvement is limited to two
  Completion decisions in the MLX case, never Active action.
- Native final text is captured only as a digest for consistency across
  OFF, healthy Shadow and Runtime-down; the private actual content, IDs,
  keys, original paths and raw logs remain Git-ignored.
- Require zero actual physical StepFun/provider requests and **zero
  automatic tool retry, model escalation or Agent stop** caused by System
  One. Existing global paid ledger must stay at 8/24 with one H1 UNKNOWN.
  Stop on any admission, evidence or cleanup issue. No result is silently
  relabelled PASS after repair; changes require a new frozen run.

## Verification and next decision

At least one fresh unmodified stock-shell OFF control must run in the same
frozen matrix as the three Shadow cases. Inspect independently recorded
actual native SQLite, post-run Hermes plugin state, HMAC-linked HTTP
observations, runtime metrics, source and model hashes, process ownership
and exact scratch restoration. Add mutation/forgery regression tests for
missing hooks, IDs, wrong actions, fake Laya counts, changed final outcome,
nonstock shell bridges and stopped/lingering processes.

Independent test judgments must use a separate `--verify` process on the
original archived evidence, not the child `PASS` label. Publishing requires
proper bounded public aggregate, clean-source tests, privacy scanner and
human-readable claims that distinguish Native Real Agent with **synthetic
main Provider**, real local Laya, and real StepFun E2E.

**Future real-provider Stage 2 is NOT authorized by this protocol.** An
independent H4D test would require new explicit owner approval of a bounded
physical request/time/cost budget and independently proven auth route,
exact upstream source and Oracle before egress. No optional historical
physical cap slots are permission to spend. Stage 3 real-Agent paired value
requires real independently verified Agent task labels (not the Agent's
answer) and sufficient eligible decisions; prefer low-risk ambiguous Retry
candidates. Phase 8D/Active readiness remains NOT AUTHORIZED.
