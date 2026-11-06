# Phase 8.3 — Native StepFun + Laya Shadow requalification protocol

**Authorization:** User approved starting bounded isolated tests after the
proposed 8-case/24-physical-request plan. Approval is limited to the existing
StepFun Step Plan subscription. It is NOT permission to purchase API credits,
enter pay-as-you-go mode, change provider, affect production Hermes/DSH, grant
Active/Canary, change safety policies, or merge code.

**Freeze:** This source/protocol must be committed before any upstream request.
Actual source SHA is recorded by each native test, not inferred from branch.

## Hard budget and safety boundaries

- Exactly one main model: stepfun/step-5-preview, through the existing Plan
  URL https://api.stepfun.com/step_plan/v1/chat/completions only.
- Its HTTP outlet is the existing per-request durable loopback budget proxy.
  All other provider routes must fail preflight. Request reservation occurs
  before network I/O and is never refunded after a timeout/unknown outcome.
- Global physical upstream calls at most 24; per-run at most 3, counting every
  auxiliary or attempted retry. Per-task native wall timeout at most 90 s.
  Stop for cap exhaustion, unverified egress, lost correlation, or unsafe data.
- Monetary or subscription-credit billing cannot be independently verified;
  a call cap is not a proved monetary cost cap. No API overage, provider
  fallback or plan top-up is permitted.
- Decision model: local cached Laya Typed Decisions 421M using MLX and an
  isolated test Runtime on port 18782; never confuse with StepFun main model.
- Adapter observer: isolated loopback port 18793. Existing unrelated local
  services and production Agent/Relay/Gateway must remain untouched.
- Private homes and task files exclusively under ignored repository private
  storage, restrictive permissions. No raw prompts, original file nonce,
  Session IDs, paths or credentials may enter public Git files or summaries.
- Default OFF/Shadow mode, never Active; no Agent auto-retry, auto-stop, model
  tier switching, paid escalation, or irreversible tool action.
- A healthy Shadow emits real Laya observations; Runtime down requires an
  HTTP 503 from the isolated collector but leaves native task execution intact.
  No Mock run will be called a real Provider pass.

## Predeclared matrix: at most eight native tests

H1 Hermes OFF read-only hidden nonce; independently verify original bytes.
H2 Hermes Shadow healthy, same read-only semantics, native→Adapter→HTTP link.
H3 Hermes Shadow Runtime-down, same read-only semantics, fail-open evidence.
H4 Hermes Shadow healthy, native missing-file read failure, no automated retry.
D1 DSH SDK OFF read-only hidden nonce with paired call/result.
D2 DSH SDK Shadow healthy, real Laya/MLX and exact request-ID correlation.
D3 DSH SDK Shadow Runtime-down, native result unchanged and HTTP 503.
D4 DSH SDK Shadow healthy, native missing-file failure, no automated retry.

A new independent input file and native run identity are required per test;
its nonce is not in the prompt. Native tool response, original file bytes and
final answer are independently checked; Agent text alone does not certify a
successful tool call. The missing-file test requires actual native failure
and the target to remain absent.

## Evidence and verdicts

- Reuse 8.2A native runner, real Plan pass-through, independent task verifier,
  8.2B capability ledger, HMAC correlation and independent native verifier.
- Only a witnessed local Runtime MLX invocation counts as model participation.
  Deterministic Retry remains a rule; unknown outcomes remain unknown.
- Every run reports source SHA, platform, mode, task, native outcome, budget
  reservations/attempts/responses, actual HTTP statuses and exact identity
  correlation. Do not associate by wall-clock proximity alone.
- Per-run verdict PASS/PARTIAL/BLOCKED, explicit missing capability when
  source events or auth unavailable; no forced overall PASS.
- Make no statistical latency generalization from 1 read per mode.
- Native Agent-level token/time/cost saving is NOT_MEASURED because this
  phase remains Shadow only.
- Leave GitHub PR as Draft without automatic merging and NAS main untouched.
