# Phase 7B — Notification parity + StepFun Step 5 Preview validation

Date: 2026-10-06

> Historical naming note: this report predates the project-level **Phase 7B —
> Unified Adapter Contract** scope adopted on 2026-10-07. The filename is retained
> to preserve validation provenance. The current Phase 7B contract is documented in
> [`docs/ADAPTER_CONTRACT.md`](../../../docs/ADAPTER_CONTRACT.md).

## 1. Scope

Phase 7B closes two follow-ups from Phase 7A without adding new control-plane surface area:

1. add **Notification Gate Shadow** to both Hermes and DeepSeek Harness so the adapters share the same three core Local System One decisions;
2. replace the temporarily degraded Nova/DeepSeek provider path with a second real Model Tier wire probe using Hermes' existing **StepFun Step Plan / `step-5-preview`** configuration.

Phase 7B does **not** add Active notification delivery, Completion Gate, Retry Gate, Action Risk Gate, cross-provider routing, probability-threshold Active routing, or global/profile model mutation.

## 2. Validation environment

| Item | Value |
|---|---|
| Host | Apple Silicon arm64 |
| macOS | 27.0 |
| Node.js | v26.6.0 |
| DSH | `0.2.1-alpha.1` |
| DSH commit | `5badb15009ae1756c3afe0ae0cef1faafc290ccc` |
| Local System One | loopback `127.0.0.1:8787` |
| ANE health | healthy, `startup_probe_passed` |
| Hermes eval profile | `systemoneeval` |

The DSH package remains fenced to the exact validated prereleases from Phase 7A. Phase 7B does not widen that peer range.

## 3. Unified three-gate semantics

The runtime owns platform-independent decisions:

```text
Search Gate        -> search / no_search
Model Tier Gate    -> fast / strong
Notification Gate  -> silent / digest / notify_now
```

Adapters own platform-specific execution. `reasoning_effort` / `reasoningEffort` remains an adapter mapping rather than part of a universal runtime contract.

Notification is deliberately **Shadow-only** in both adapters. `notify_now` is recorded as evidence but has no delivery authority.

## 4. Hermes Notification Shadow

Hermes exposes the required production lifecycle hooks:

```text
post_llm_call
on_session_end
```

Phase 7B uses them as follows:

```text
post_llm_call
  -> hold bounded final assistant event in process-local memory
on_session_end
  -> combine lifecycle facts
  -> POST /v1/workflows/notification-gate
  -> persist decision metadata only
  -> discard raw event
```

The persisted state contains only fields such as delivery, notify flag, reason, score, confidence, backend, latency and event character count. Raw final-response text is not persisted.

A failed turn with no final response may submit a synthetic failure event with `blocking_failure=true`. Interrupted turns do not automatically claim blocking failure.

### Hermes live evidence

The `systemoneeval` profile was upgraded from the previously installed `0.5.1` plugin to `0.6.0` using the profile-aware atomic installer.

The live smoke established:

- OFF: no Local System One call — PASS;
- Shadow Search Gate: `bounded_transform_task` — PASS;
- Shadow Model Tier Gate: `fast / bounded_transform` — PASS;
- Shadow Notification Gate: `digest`, `notify_now=false` — PASS;
- Notification backend: `ane` — PASS;
- persisted Notification state contained `event_chars=176` and decision metadata, not raw response text — PASS.

The legacy multi-stage live smoke exceeded the command-session runtime limit before its Canary/fail-open stages completed. The evaluation profile was explicitly restored to:

```text
mode=shadow
canary_acknowledged=false
service_url=<unset, default loopback>
```

Canary/fail-open behavior is unchanged by Phase 7B and remains covered by the Hermes plugin regression suite.

## 5. DSH Notification Shadow

DSH `session/event` is an observe-only event contract. Listener promises are not awaited by the main loop and listener failures are contained. That makes it appropriate for Shadow telemetry, but not yet for Active delivery authority.

Phase 7B observes:

```text
assistant/message
  -> keep the last bounded visible assistant text for session+turn
turn/end
  -> POST /v1/workflows/notification-gate
  -> log decision metadata only
  -> clear transient event text and turn state
```

A blocking failure with no visible assistant event uses a generic synthetic failure event. No raw response is stored in adapter state or logs.

### Real three-gate E2E

A privacy-safe local HTTP proxy recorded only request paths and JSON field names. One completed DSH + StepFun turn produced all three runtime calls:

```text
POST /v1/workflows/search-gate
POST /v1/workflows/model-tier-gate
POST /v1/workflows/notification-gate
```

The Notification request shape contained only the expected contract keys:

```text
blocking_failure
context
event
request_id
routine_update
urgency
user_action_required
```

The proxy did not record task text, event text, system prompts, credentials or full provider headers.

## 6. StepFun provider discovery

Hermes' existing provider configuration identified:

```text
provider: stepfun
label: StepFun Step Plan
base URL: https://api.stepfun.com/step_plan/v1
credential env: STEPFUN_API_KEY
model: step-5-preview
canonical model: stepfun/step-5-preview
```

The credential value was never printed, logged or committed.

Hermes model metadata reports `step-5-preview` as reasoning-capable with effort values:

```text
low
medium
high
```

This metadata was treated only as a probe hypothesis; Active compatibility was not granted until real provider-wire tests passed.

## 7. StepFun provider-wire probe

A privacy-safe local forwarding proxy was placed between DSH and the existing StepFun endpoint. It logged wire shape only.

### Native high

DSH configuration:

```text
provider=stepfun
model=step-5-preview
reasoningEffort=high
```

Observed provider request:

```text
POST /step_plan/v1/chat/completions
model=step-5-preview
reasoning_effort=high
stream=true
tools=24
```

Result: provider completion succeeded and returned `STEPFUN_DSH_HIGH_OK`.

### Native low

DSH configuration:

```text
reasoningEffort=low
```

Observed provider request:

```text
reasoning_effort=low
```

Result: provider completion succeeded and returned `STEPFUN_DSH_LOW_OK`.

Therefore the DSH StepFun adapter maps `reasoningEffort` into the actual StepFun provider wire, and both tested effort values are accepted by the live endpoint.

## 8. Local System One automatic Model Tier Canary

The bounded transform probe returned:

```text
tier=fast
decision_source=rule
reason=bounded_transform
backend=rule
confidence=1.0
```

DSH started the turn at:

```text
stepfun / step-5-preview / reasoningEffort=high
```

With acknowledged Canary and `canary_reasoning_downgrade_enabled=true`, the real provider wire became:

```text
reasoning_effort=low
```

The StepFun completion succeeded.

`stepfun/step-5-preview` therefore joins the exact verified Model Tier route allowlist.

## 9. Tool-loop restoration

A real task forced DSH to use the local `read` tool before answering. The Local System One rule still classified the turn as deterministic `bounded_transform`.

Observed StepFun provider sequence:

```text
provider call 1: reasoning_effort=low
provider call 2 after tool result: reasoning_effort=high
provider call 3 after tool result: reasoning_effort=high
```

The final answer succeeded and reported the repository package name from the tool result.

This confirms the mutation remains local to the first provider call and does not leak into the subsequent tool loop.

## 10. Safety properties retained

Phase 7B preserves the Phase 7A control boundaries:

- installation defaults to OFF;
- Canary requires explicit acknowledgement;
- Model Tier probability never gains Active authority;
- only audited deterministic hard-fast reasons may mutate reasoning effort;
- provider/model matching is exact;
- mutations are copy-on-write and first-provider-call only;
- Search hard no-Web allowlists are unchanged;
- each gate fails open;
- Notification is observation-only;
- no credential values are logged or committed;
- transient Notification text is cleared after the turn.

## 11. Parity matrix

| Capability | Hermes | DSH | Phase 7B result |
|---|---:|---:|---|
| Search Shadow | yes | yes | aligned |
| Search deterministic Canary | yes | yes | aligned |
| Model Tier Shadow | yes | yes | aligned |
| Model Tier deterministic Canary | experimental | experimental | aligned semantics |
| Notification Shadow | yes | yes | **newly aligned** |
| Notification Active delivery | no | no | intentionally NO-GO |
| Independent gate switches | yes | yes | aligned |
| Fail-open | yes | yes | aligned |
| Turn-scoped cleanup | yes | yes | aligned |
| Probability-based Active authority | no | no | aligned |

Platform-specific execution remains intentionally different: Hermes and DSH do not share identical tool names or provider request objects.

## 12. GO / NO-GO

**GO**:

- Hermes Notification Shadow `0.6.0`;
- DSH Notification Shadow `0.3.0`;
- StepFun Step Plan / `step-5-preview` as a verified DSH Model Tier Canary route;
- continued Unified Adapter Contract work using runtime decisions plus platform-owned mappings.

**NO-GO**:

- Active Notification delivery;
- probability/score-threshold Model Tier mutation;
- unverified provider/model aliases;
- cross-provider model switching;
- widening DSH prerelease compatibility without a new lifecycle + provider-wire probe.

## 13. Final regression

Final repository QA after the Phase 7B changes:

```text
Python repository suite: 81 / 81 PASS
Hermes focused plugin suite: 22 / 22 PASS
Hermes plugin validate: PASS
Hermes plugin doctor --ci: PASS
DSH adapter suite: 35 / 35 PASS
DSH TypeScript typecheck: PASS
DSH build: PASS
npm audit: 0 vulnerabilities
npm pack --dry-run: PASS (v0.3.0, dist included)
git diff --check: PASS
secret-pattern scan: PASS
```

## 14. Release posture

This phase should be reviewed and merged through the normal repository flow:

```text
feature branch -> NAS Forgejo origin -> review -> public GitHub
```

No production Hermes profiles need to be changed for validation. The only live Hermes profile touched in Phase 7B was the dedicated `systemoneeval` evaluation profile.
