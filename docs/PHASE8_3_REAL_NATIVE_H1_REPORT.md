# Phase 8.3A — First real StepFun native H1 trial

**Executed 2026-10-21. H1 agent task PASS, global native-provider
engineering acceptance BLOCKED.** This is *not* a mock replay and is not
a Laya vs rule quality result.

## 1. Test identity, prior authorization and scope

- Native platform: Hermes v0.22.1, explicitly separate new test Home.
- Frozen execution source commit: 82993477667817c8941caa429feea576d091a424.
- Main model: real StepFun Step Plan step-5-preview.
- Decision platform: System One OFF, therefore **no Laya call or observer
  network traffic was expected**. Shadow MLX validation remains future work.
- Scenario: one native read_file of a disposable private input file,
  whose content was withheld from the task prompt. No task mutation.
- Provider egress: local loopback HTTP port 18794, forwarding only
  the Step Plan HTTPS chat/completions endpoint.
- Explicit authorized caps: 24 global physical requests, 3 physical
  requests this run, 90 s Agent-native task timeout.
- Existing default Hermes config, production Gateway, NAS main,
  model threshold and Canary/Active permissions: not changed.

## 2. Native Agent: successful independent read

The user-facing Agent returned with process exit 0, no task timeout,
and **27.343 s of measured native-run wall time**.

The independent verifier checked the actual isolated Hermes SQLite
tool/message records, not only the Agent's final text. It confirmed:
- exactly one read_file native tool invocation and paired native result;
- the native tool result contained the exact private original file bytes;
- the final Agent answer contained the same original content;
- the fixture content was absent from the user's task prompt;
- the native record's primary billing route was the audited local proxy;
- original private input remained unchanged and the native Session
  finished normally.

The Phase 8.2A original source verifier is used here as a strict
single-task oracle. It is not a general proof of arbitrary Agent tool
correctness or reasoning accuracy. Raw bytes, prompts, native Session
identity and SQLite records remain in the Git-ignored private directory.

**Task-only verdict: PASS_SCOPED.**

## 3. Provider lifecycle: incomplete; do not silently repair evidence

The already implemented bounded pass-through ledger recorded:

| Strict physical request counter | Observed |
|---|---:|
| Durable reservations before network I/O | 3 |
| Actual attempted outbound HTTPS requests | 3 |
| Provider response observed, HTTP 200 | 2 |
| Provider response explicitly marked failed | 0 |
| Attempted with no terminal response/unknown marker | **1** |
| Proxy finalized requests | 2 |
| Proxy reservations never recovered/refunded | 3 |
| Further requests passed through this run | 0 |

**The unresolved slot is slot 1.** Its origin and real billing or
execution outcome are UNKNOWN. The ledger does not contain any
Provider response for it. It must not be renamed an auxiliary request,
backfilled as HTTP 200, assumed free or removed from the denominator.

The native Agent usage summary separately reported **2 main-model API
calls**, client-side input 7,238 tokens, output 287 tokens and zero
self-reported auxiliary calls. This is *Agent-reported* accounting and
not Provider-confirmed token usage or billing. Consequently the
independent budget reconciler reports **1 unattributed physical
request** (3 physical - 2 reported logical).

The independent Phase 8.2B budget reconciler returned:

- Budget integrity: **BLOCKED**.
- Explicit issue: reserved_without_proxy_result.
- Attempted unresolved: **1**.
- Unattributed requests: **1**.
- Unknown cost requests: **3**.
- Plan credit consumption / actual monetary charge: **UNKNOWN**.

The original H1 runner stopped its provider proxy immediately after
the Agent native process completed. That could have truncated a still
in-flight, initially reserved HTTPS request. This is a **plausible
test-harness lifecycle flaw**, not verified proof of the request's
contents, purpose or ultimate billing. The missing terminal record
is irrecoverable from the captured artifacts; we will not fabricate it.

## 4. Defensive correction after the frozen run

A separate later implementation changed only the *test harness* to
wait, for an explicitly bounded interval, for **already attempted**
provider requests to reach a ledger terminal state before stopping
the real proxy. The upstream transport's own timeout remains the
enforcing upper bound; the drain does not create any new request.

This fix was **not present in the original H1 frozen execution source**,
has no new Provider-backed acceptance evidence and does not make H1
budget integrity pass retroactively. H1 is intentionally a one-shot
case, not rerun to improve the appearance of the result.

The independent public aggregate is at
results/processed/phase8_3_h1_real_stepfun_partial.json, generated
from the original private real ledger and independently checked native
source. It contains only allowlisted counts and SHA-256 digest, never
the original private task data or credential.

## 5. Requalification and decision

| Gate | Result |
|---|---|
| H1 native OFF read-only business task | PASS, scoped |
| H1 real StepFun main path | OBSERVED, two HTTP 200 |
| Global physical per-task request ceiling | PASS, 3/3 reserved |
| H1 provider request terminal accounting | BLOCKED, one unresolved |
| H1 Laya model participation | NOT APPLICABLE, OFF |
| H2 Hermes healthy Shadow | NOT RUN |
| H3 Hermes Runtime-down Shadow | NOT RUN |
| H4 Hermes failed-read Shadow | NOT RUN |
| D1-D4 DSH real native tasks | NOT RUN |
| Live post-8.2B native Adapter-to-HTTP HMAC | NOT VERIFIED |
| Native Agent performance/real-world value delta | NOT MEASURED |
| StepFun Plan credits and actual fees | UNKNOWN |
| Active/Canary | NOT AUTHORIZED |

**Phase 8.3A overall: BLOCKED**, despite legitimate H1 native task
success. We STOP further real Provider calls until the incomplete
outbound reservation/attempt is understood and the updated lifecycle
accounting/egress controls are independently qualified. Three of the
original 24 experimental request slots were permanently consumed;
21 mathematically remain, but these are **not usable authorization
while the test is blocked**, nor a statement about subscription credits.

PR #9 remains Draft. No automatic merging, production modifications or
new paid Provider was used.

## 6. Final software regression and release boundary

Following the real run, a separate verifier and tests were added on top
of the original frozen test-source SHA. All 80 new synthetic holdout
records and the prior 210 historical public examples remain untouched.

Full Python regression **1082/1082 PASS**, DSH Vitest **64/64 PASS**,
TypeScript typecheck PASS and build PASS. These are engineering regression
checks, **not additional paid StepFun calls** and cannot reclassify the
one unresolved physical request.

A privacy-filtered 8.3 H1 aggregate is committed independently of its
original private evidence. Original raw native messages, test file
content, Provider credentials, HTTP request bodies, and Session identifiers
were not added to Git. Release sanitizer and clean-source checks are
separate final publication gates.

**Phase 8.3A remains BLOCKED for further real Provider experiments
until the missing request lifecycle is investigated**, despite this
successful offline regression.
