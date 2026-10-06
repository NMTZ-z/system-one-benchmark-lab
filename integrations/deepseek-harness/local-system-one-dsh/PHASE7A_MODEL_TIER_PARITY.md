# Phase 7A — DeepSeek Harness Model Tier Parity

Date: 2026-10-06

## 1. Scope

Phase 7A brings `local-system-one-dsh` from Search-only Phase 1 to core **Search + Model Tier** parity with the Hermes integration, without adding new gate families.

Implemented scope:

- independent Search Gate and Model Tier Gate switches;
- Model Tier Shadow observation with privacy-safe metadata only;
- existing Search hard-rule Canary preserved;
- experimental Model Tier Canary only for deterministic audited hard-fast rules and an exact verified provider/model route;
- fail-open isolation between gates;
- per-turn lifecycle cleanup;
- Unified Adapter Contract preparation that keeps runtime tier semantics platform-neutral.

Explicitly excluded: Completion, Retry, Action Risk, Notification, probability-threshold active routing, cross-provider routing, profile/global mutation, and new custom agent loops.

## 2. DSH versions inspected

| Target | Version / tag | Commit | Result |
|---|---|---|---|
| historical baseline | `dsh-v0.1.7-rc.2` / `0.1.7-rc.2` | `477b4f420553e8a52c2fbccc464d7561b239c443` | full lifecycle + successful provider E2E captured in this phase |
| current upstream probe | `dsh-v0.2.1-alpha.1` / `0.2.1-alpha.1` | `5badb15009ae1756c3afe0ae0cef1faafc290ccc` | build PASS; lifecycle and actual provider-wire mutation PASS; final completion currently blocked by the same Nova route error reproduced on rc2 |

Validation host observed during the phase: Apple Silicon arm64, macOS `27.0 (26A428)`, Node `v26.6.0`, pnpm `11.7.0`.

The package compatibility fence is deliberately exact:

```text
@deepseek-ai/dsh-agent: 0.1.7-rc.2 || 0.2.1-alpha.1
```

The first alpha probe initially appeared to leave `reasoning_effort=high`; stderr showed why: DSH had correctly disabled plugin `0.1.0` because its peer fence allowed only rc2. After revalidation and the `0.2.0` fence update, alpha loaded the plugin and the main provider wire contained `reasoning_effort=low`.

## 3. DSH lifecycle and provider-wire probe

Relevant DSH hooks remain present in both inspected versions:

- `agent/pre-step`
- `agent/request`
- `tools/pre-execute`
- `session/event`

`agent/request` is a waterfall around a provider-call config containing at least:

```text
provider
model
reasoningEffort?
temperature?
maxTokens?
stop?
```

The real Nova / DeepSeek request path observed through a privacy-safe local proxy was:

```text
POST /v1/chat/completions
```

Observed main-agent wire metadata included:

```text
model
developer/user message roles
reasoning_effort
stream / stream_options
max_completion_tokens
tools
store
```

No credential value, message text, system prompt, full tool schema, or raw tool arguments were logged by the proxy.

Observed wire audit:

| Concern | DSH / wire observation | Routing conclusion |
|---|---|---|
| provider | DSH `provider=nova`; provider name is not serialized into OpenAI JSON | provider routing is a DSH-side adapter/base-URL selection |
| model | `model=deepseek-v4-flash` serialized in request JSON | model routing is directly visible on the provider wire |
| reasoning | DSH `reasoningEffort=high/low` became `reasoning_effort=high/low` | reasoning routing is supported by the validated DSH Nova adapter |
| sampling | `temperature` and `top_p` were absent/null in the observed main requests | Phase 7A does not mutate sampling |
| tools | main request advertised 24 tools during the probe, including `web_search` and `web_fetch` | tool exposure remains DSH-native except audited Search Canary |
| messages/system | roles included `developer` + `user`; the proxy recorded shape/roles only | system/developer content is not logged or copied into adapter state |
| metadata | no provider metadata keys observed | Phase 7A does not inject metadata |
| auth | authorization presence recorded as boolean only | credentials were neither printed nor persisted |

For the validated route, changing DSH `reasoningEffort` from `high` to `low` changed the actual provider JSON field from `reasoning_effort: high` to `reasoning_effort: low`.

## 4. Phase 7A-1 — Model Tier Shadow

`agent/pre-step` evaluates only `step === 1`.

Search and Model Tier are independent. Enabling one does not require enabling the other. One gate failing does not suppress the other.

Model Tier calls:

```text
POST /v1/workflows/model-tier-gate
```

The adapter stores only decision metadata. Raw task text and conversation content are not persisted in adapter state.

`turn/end` removes both Search and Model Tier state for that turn; `session/end` / `session/close` clears session state.

Shadow never mutates provider config or tools.

## 5. Phase 7A-2 — real provider/model probe

The provider route inherited from the previously working Hermes/Nova path is:

```text
provider: nova
model: deepseek-v4-flash
human label: DeepSeek V4.1 Flash
```

This phase verified that rc2 can carry `reasoningEffort` into Nova's OpenAI-compatible wire and that the provider had accepted both high and low during successful E2E runs earlier in the phase.

A later same-day rerun found a provider-side degradation:

- `deepseek-v4-flash`: both **high and low** returned the same `400 INVALID_REQUEST` on both rc2 and alpha controls;
- `deepseek-v4.1-flash`: returned `403 model is not available in the current token plan`.

Because the high control fails identically, the late 400 cannot be attributed to the Model Tier downgrade. Because the exact `deepseek-v4.1-flash` ID is unavailable to the current token plan, it is not added to the active route allowlist.

## 6. Phase 7A-3 — Canary authority

Model Tier Canary is disabled by default and requires every condition below:

1. configured mode is `canary`;
2. `canary_acknowledged=true`;
3. Model Tier Gate is enabled;
4. `canary_reasoning_downgrade_enabled=true`;
5. runtime decision is `tier=fast`;
6. `decision_source=rule`;
7. `backend=rule`;
8. reason is an audited hard-fast reason;
9. provider/model is an exact verified route;
10. original provider config has `reasoningEffort=high`.

Audited hard-fast reasons come from the runtime's deterministic rule path:

```text
bounded_transform
bounded_structured_transform
```

Current active route:

```text
nova/deepseek-v4-flash
```

The adapter uses copy-on-write mutation:

```text
{ ...original, reasoningEffort: 'low' }
```

It does not rewrite provider, model, profile, or global configuration.

A real rc2 tool-loop probe showed:

```text
turn 1 / step 1: high -> low
turn 1 / step 2: high
```

so the downgrade is not repeated after tool execution.

Model-probability decisions, score thresholds, unsupported provider/model routes, unacknowledged Canary, non-high original settings, and any exception remain pass-through.

## 7. Tests and regression

Adapter test suite after Phase 7A:

```text
29 / 29 PASS
TypeScript typecheck PASS
build PASS
npm audit: 0 vulnerabilities
```

Coverage includes:

- OFF zero-call behavior;
- Shadow Search + Model Tier once on step 1;
- independent gate switches;
- failure isolation between gates;
- unacknowledged Canary -> Shadow;
- Search deterministic hard deny;
- Search model/probability decision cannot deny;
- Search Canary feature switch;
- Model Tier deterministic hard-fast high->low copy-on-write;
- Model Tier model/probability decision cannot activate;
- unsupported provider/model pass-through;
- reasoning feature switch off;
- non-high original setting preservation;
- tool-loop step 2 no repeat mutation;
- dead-service / malformed-response fail-open;
- turn cleanup / cross-turn isolation.

The previous Search Gate audited reason set and exact public-Web tool allowlist are unchanged.

## 8. Hermes parity acceptance matrix

| Capability | Hermes | DSH 0.2.0 | Phase 7A result |
|---|---:|---:|---|
| OFF | yes | yes | PASS |
| Search Shadow | yes | yes | PASS |
| Model Tier Shadow | yes | yes | PASS |
| independent gate switches | yes | yes | PASS |
| explicit Canary acknowledgement | yes | yes | PASS |
| deterministic Search Canary | yes | yes | PASS |
| model-probability Search active authority | no | no | PASS |
| deterministic Model Tier Canary mechanism | yes, platform-specific | yes, platform-specific | PASS |
| Model Tier Canary default | off | off | PASS |
| fail-open | yes | yes | PASS |
| turn-scoped cleanup | yes | yes | PASS |
| copy-on-write provider mutation | yes | yes | PASS |
| provider/model allowlist | platform-specific | platform-specific | PASS |
| rollback to native behavior | yes | yes | PASS |

Parity here means safety and capability parity, **not identical provider knobs**. Hermes and DSH are allowed to map `tier=fast/strong` differently.

## 9. Unified Adapter Contract preparation

The reusable cross-platform contract should stop at platform-neutral facts:

```text
gate identity
request / turn identity
abstract decision (for example fast / strong)
decision source
reason
confidence / probability / scores
backend / latency
whether deterministic active authority exists
```

The runtime owns the tier semantics and audited rule reasons.

Each platform adapter owns the concrete mapping from that tier to its local execution mechanism. For DSH, the currently verified experimental mapping is a one-request `reasoningEffort` downgrade on one exact Nova route. Hermes may use a different provider-specific mechanism. Future Codex / Claude Code adapters should not be forced to expose a Hermes-shaped `reasoning_effort` field.

This separation is the recommended basis for a later Unified Adapter Contract.

## 10. GO / NO-GO

**GO** for `local-system-one-dsh v0.2.0` as the Phase 7A adapter release candidate with these constraints:

- OFF remains the installation default;
- Search and Model Tier Shadow are production-safe observation modes;
- Search Canary keeps its existing audited hard-rule boundary;
- Model Tier Canary remains experimental, explicitly acknowledged, feature-switched, exact-route-only, and disabled by default;
- no probability-based active routing;
- no cross-provider/model rewrite;
- no global/profile mutation.

**Current Nova caveat:** a late provider rerun on 2026-10-06 returned the same 400 for native high and mutated low requests on both rc2 and alpha; the exact `deepseek-v4.1-flash` ID returned 403 for the current token plan. This is recorded as a provider availability blocker for fresh completion-level repro, not as an adapter regression. The earlier successful rc2 provider E2E and tool-loop E2E remain the acceptance evidence for the verified route.

Rollback is immediate: Canary -> Shadow -> Off -> disable/remove plugin. No Hermes configuration or other DSH profile/provider configuration is modified by the adapter.
