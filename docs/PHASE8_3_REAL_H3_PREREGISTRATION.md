# Phase 8.3A — H3 native Runtime-down one-shot preregistration

**Written before any H3 real StepFun Plan Provider traffic, 2026-10-21.
H3 is part of the originally user-authorized eight-case bounded matrix.
No Active or Canary authorization.**

## Research question

Can the real Hermes Agent, with the actual StepFun Step Plan
step-5-preview main model, complete a native read-only file task while
the local Laya Runtime is physically **down**, with two isolated Shadow
Completion observations correctly reported as HTTP 503 / fail-open
without changing Agent execution?

Second, a *nonconfirmatory engineering hypothesis*: Hermes v0.22.1
launches an asynchronous model-generated session title by default.
H1/H2 each had three physical StepFun requests against two main-Agent
reported calls. H2's first request lasted 33.13 s while its native
Agent ended in 29.581 s. Source shows a concurrent title model call
with a bounded 10-second oneshot join. The test Home had default title
model upgrade enabled, but historical physical slots have no saved
request-purpose label, so **actual source attribution remains unknown**.

For H3 only, disable auxiliary.title_generation.model_upgrade_enabled
while retaining deterministic derived titles. This controls one extra
background LLM candidate but is not a randomized experiment, and
H3 is otherwise a distinct Runtime-down task. Two vs two physical/main
calls would *support*, not conclusively prove, the title hypothesis.

## Frozen provenance / native policy

- GitHub and NAS main remain unchanged, Phase 8.3 PR stays Draft.
- Real H1 native original SHA:
  82993477667817c8941caa429feea576d091a424.
- Real H2 native original SHA:
  0dc626ff86038702f74027b4a988d21f096f72d9.
- Historical H1 first 10 provider-ledger rows SHA-256:
  bded2cecb79bcf22a6cdb39a4186b99fb68e881651d18142de370e3b120133de.
- Historical H1+H2 first 22 rows SHA-256:
  dbd2be172785d94ded75e264be1534f4f9396a33edf4bb4f555492604b6a7b3f.
- A separate secure ignored snapshot of the H1+H2 exact ledger
  is preserved for independent H2 replay after H3 append-only events.
- Current H3 candidate source, this protocol, native runner and
  public release allowlist MUST be committed before any real Provider
  request. Results must cite this exact preregistration commit.
- The previously authorized existing StepFun Plan
  step-5-preview via https://api.stepfun.com/step_plan/v1/chat/completions
  is the ONLY upstream, mediated by the local 127.0.0.1:18794
  Provider-cap gateway. No pay-as-you-go key or second Provider.
- Global maximum 24 reserved physical requests, H3 maximum 3,
  6 already consumed by H1+H2. No resetting or refunding H1 unknown.
- H3 Laya Runtime: intentionally NO listener on port 18782.
  Observer on port 18793 forwards to the absent local runtime and
  records actual HTTP 503, with null backend. No local model
  inference is credited during this failure-control test.
- Native Hermes Shadow task: exactly one read_file of a new random
  private disposable original file, whose nonce is NOT in the task
  prompt. No writes, network tools, shell, browser or Active action.
  The native task hard timeout is 90 seconds, and proxy drain can
  only await already-requested transport, up to 80 more seconds.
- New plugin observation events are compared with a pristine
  pre-test adapter history; strict native SQLite + keyed Adapter
  + actual observer HTTP request refs establish causal identity.
  A 503 cannot echo a success response ID; never fabricate one.
- All original private files, prompts, native Agent logs, raw
  Provider bodies, API keys, HMAC key and Session/Turn IDs stay
  outside public Git, under restricted ignored private storage.

## Predeclared H3 acceptance

Scoped H3 PASS requires every item below.

1. Exact clean Git source, isolated manually authenticated StepFun
   credential and correct pinned proxy URL, OFF/Shadow-only.
2. The new isolated config has title model-upgrade disabled, while
   its previous H1/H2 run sources and historical ledger remain frozen.
3. Provider cap 24 total and three in H3 (or fewer); every H3
   attempted request must have an actual final response/unknown
   marker and proxy result. If unknown, the H3 verdict is BLOCKED.
4. Independently verified native read_file tool call/result identity,
   unchanged original file bytes, final answer match and normal exit.
5. Two true observer HTTP 503 events, zero local inference backend,
   two Adapter failed_open observations, 2/2 exact
   native→Adapter→observer HTTP keyed request links.
6. Isolated Hermes test Home is restored to OFF; no production change.
7. H1 unresolved remains 1; global Phase8.3A stays BLOCKED;
   actual Provider billing, Agent token savings and active readiness
   are NOT ESTABLISHED.

Any missed criterion = PARTIAL_OR_BLOCKED; no automatic H3 rerun and
no immediate H4/DSH paid tasks. Synthetic local observer/proxy tests
do not substitute for fresh real native StepFun evidence.

## Prerequisite gates

Before real H3: local faults and error-path tests PASS, historical
ledger SHA verified, full Python/DSH regressions PASS, privacy-safe
public release sanitizer PASS, isolated title-migration completed
without Provider calls, clean frozen source committed. Every external
request continues to count against existing original 24 slots.
