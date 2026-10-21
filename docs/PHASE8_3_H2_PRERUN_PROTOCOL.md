# Phase 8.3A — Hermes real StepFun / Laya Shadow H2 pre-run freeze

**2026-10-21. This protocol is committed BEFORE any H2 real main-Provider
execution.** The owner explicitly authorized continued bounded Phase 8.3A
native Shadow validation. This only covers ONE H2 task. It does not
authorize Active, budget increases, a second paid provider, or merge.

## What is known at the pre-run boundary

- Previous H1 real StepFun native OFF read: native tool/file oracle PASS,
  3 physical requests attempted, 2 recorded HTTP 200, **one missing
  terminal record (H1 slot 1)**. H1 budget reconciliation remains BLOCKED.
  Never invent a response, change or delete this ledger record.
- Corrective Provider-drain control was implemented AFTER H1, so H1
  evidence does not certify the fix.
- Independent LOCAL fake-Provider integration: seven scenarios PASS.
  They include delayed streaming, Agent-side disconnect, unknown
  upstream outcome, H1 prefix tampering, undeclared run IDs and
  physical request limits. All fake traffic was loopback-only.
- Actual cached Laya MLX Runtime + local observer separately handled
  two Completion probes with HTTP 200 / backend=mlx /
  decision_source=model, HMAC reference and echo-ID matching. No
  main StepFun call was made.
- These results justify only a NEW, scoped H2 test. They cannot make
  the historical H1 budget reconciliation PASS.

## Exactly one predeclared H2 native task

| Dimension | Fixed plan |
|---|---|
| Agent | Official Hermes native one-shot CLI, isolated test Home |
| Main model | StepFun Step Plan step-5-preview ONLY |
| Physical outlet | 127.0.0.1:18794 capped Provider proxy |
| Local decision model | Cached Laya Typed Decisions 421M, MLX |
| Policy | Shadow-only Completion/Retry observers, never Active |
| Isolated Runtime/observer | 127.0.0.1:18782 / 127.0.0.1:18793 |
| Scenario | One read-only native read_file of a NEW random hidden nonce |
| Independent oracle | Original bytes, native SQLite call/result IDs, result contents, final text |
| Request budget | H1's previous 3 remain counted; max 24 global, max 3 for H2 |
| Time bounds | 90 seconds native, up to 80 seconds for existing in-flight provider closeout |
| Evidence | Private HMAC native/Adapter/HTTP join and actual Runtime backend |
| Storage | Git-ignored private H2 run, no overwrites |
| Production | Default Hermes/Gateway, NAS and GitHub main untouched |

The H2 run must reuse the SAME original H1 private physical ledger,
never reset the previous count. Before native execution, the H1
first-ten-event SHA256 must equal:

bded2cecb79bcf22a6cdb39a4186b99fb68e881651d18142de370e3b120133de

Preserve H1 slots 1,2,3, one unresolved, and require no preexisting
H2 slots. Keep a clean pinned Git worktree and individually attest
the user-owned test-home manual credential to the local cap proxy.

The hidden nonce must not be in the Agent's prompt. No file writes,
shell, browser, external network tool, user account or production
file may be accessed for this task.

## Evidence criteria

**H2 PASS only if all apply:**
- Native Agent exits normally; original input remains unchanged;
  independent SQLite native tool result/call IDs, byte contents,
  final answer and file oracle all agree.
- Every H2 physical call has a pre-send durable reservation, valid
  attempted/terminal response and proxy result, with no H2 unknown
  terminal outcome, duplicate or out-of-scope Provider request.
- The shared global Provider cap remains at 24, and H2 has at most
  three real physical attempts. H1 historical unresolved remains
  explicitly present and permanently counted.
- Exactly two H2 Completion Shadow observations return HTTP 200,
  backend=mlx, echo the request identity and match native/Adapter/HTTP
  evidence through the private HMAC key. Their suggestions change
  no Agent execution or tool permission.

Any failure, lack of provenance or unknown request ends the run
PARTIAL/BLOCKED; do not retry H2. No Mock substitute, no extra Provider,
no backup identity and no broader cap. Stop owned services and retain
all original raw data only in the private test area.

Even a scoped H2 PASS cannot change the Phase 8.3A overall blocked
H1 budget history, and cannot prove real Agent quality superiority,
production latency parity, monetary cost or savings.

## Pre-run identity

H1 execution source: 82993477667817c8941caa429feea576d091a424.
H2 execution SHA must be a separate later frozen commit.
Status at this point: H2 NOT YET RUN. No real H2 StepFun calls.


## Final preregistration QA

Before any H2 real Provider request, the Python full regression passed
**1102/1102**, DSH Vitest **64/64**, TypeScript typecheck and build
PASS. This includes new real-local Laya/MLX smoke, mocked slow/stopped
Provider transport, immutable H1 budget prefix, HMAC causal correlation
fixtures, native identity/nonce restrictions, and overlapping ledger
append/read lock tests. Offline tests never invoke StepFun.

The native H2 source, transport closeout code, test definitions and
this protocol will be committed together before any main-Provider
traffic, and the H2 runner refuses a dirty checkout or wrong
frozen source SHA. The pre-run actual H2 native task remains
NOT RUN at the point of this preregistration.
