# Local System One Adapter Contract v1

Local System One is a platform-independent **Agent Decision Plane**. The Runtime
decides what an agent should do; a platform Adapter decides whether and how that
decision can be applied on a specific agent runtime.

Contract version: `1.0`

Machine-readable reference: [`contracts/adapter-contract-v1.schema.json`](../contracts/adapter-contract-v1.schema.json)

This contract is deliberately small. It was extracted from two real integrations,
Hermes and DeepSeek Harness (DSH), rather than designed as a speculative framework.

## 1. Architecture

```text
                    Local System One
                           |
                           v
                   Decision Contract
                           |
           +---------------+---------------+
           |                               |
           v                               v
     Hermes Adapter                   DSH Adapter
           |                               |
   Hermes lifecycle                  DSH lifecycle
   Hermes tools                      DSH tools
   Hermes provider                   DSH provider
           |                               |
           v                               v
        Hermes                           DSH
```

The shared layer contains decision semantics and observation vocabulary. It does
**not** contain platform tool names, provider objects, request objects, hooks, or
provider-specific controls such as `reasoning_effort`.

## 2. Phase 7B audit: repeated concepts before extraction

| Concern | Runtime | Hermes before v0.7.0 | DSH before v0.4.0 | Phase 7B resolution |
|---|---|---|---|---|
| Search semantics | `search` / `no_search` | understood same values | understood same values | canonical `search` Decision Envelope |
| Model Tier semantics | `fast` / `strong` | mapped `fast` to one verified Hermes reasoning control | mapped `fast` to verified DSH provider routes | canonical `model_tier` Decision Envelope; mapping stays local |
| Notification semantics | `silent` / `digest` / `notify_now` | Shadow only | Shadow only | canonical `notification` Decision Envelope |
| Modes | Runtime is mode-agnostic | `off` / `shadow` / `canary` | same | shared mode vocabulary |
| Canary acknowledgement | Runtime does not grant authority | explicit acknowledgement | explicit acknowledgement | Adapter-owned authority; `decision != permission` |
| Gate switches | Runtime endpoints independent | independent config switches | independent config switches | common Gate Configuration concept |
| Fail-open | Runtime reports/raises failures | aggregate Search+Tier call status could suppress a healthy gate | gate-local failures already isolated | Hermes changed to gate-local fail-open; both preserve platform behavior |
| Turn state | no platform lifecycle | Hermes `ctx.state`, turn id | session + numeric turn state | lifecycle remains platform-specific; minimal Turn Context only |
| Search mutation | none | hides `web_search` / `web_extract` | denies verified DSH Web tool names | same decision, different platform action |
| Model mutation | none | verified Hermes request mutation | verified provider/request mutation | `fast` stays semantic; no provider field enters contract |
| Telemetry | workflow result fields | plugin-state metadata | structured logs | versioned common comparison fields + platform extensions |
| Privacy | service does not persist raw requests by default | no raw task persisted; bounded notification text ephemeral | no raw task/transcript persisted | raw transcript/system prompt/credentials excluded from contract |

One material mismatch was fixed during this audit: Hermes previously wrapped Search
and Model Tier calls in one success flag. If Search succeeded and Model Tier timed
out, a valid Search Canary decision lost authority. v0.7.0 evaluates success per
gate, matching DSH's existing independent fail-open behavior.

## 3. Runtime responsibility

The Runtime owns:

- Gate decision semantics;
- deterministic rules;
- typed-model inference;
- scores, probabilities, and confidence where meaningful;
- decision reasons and backend routing;
- request validation for Runtime workflows.

The Runtime does **not** own platform execution authority. A result such as
`tier=fast` never means "set reasoning effort to low". It means only that the
Runtime considers the task eligible for the abstract fast tier.

The existing Runtime HTTP API is unchanged in v1. Adapters normalize current
workflow responses into the contract at their boundary.

## 4. Adapter responsibility

An Adapter owns:

- platform hooks and turn/session lifecycle;
- state lifetime and cleanup;
- tool-name mapping;
- provider/model mapping;
- request/tool mutation;
- Canary eligibility and execution authority;
- fail-open behavior and rollback;
- platform-version compatibility.

Platform-specific objects stay inside the Adapter. They are not Runtime schema.

## 5. Decision Envelope

The common envelope contains only fields that both current Adapters can use without
inventing fake values:

```json
{
  "adapter_contract_version": "1.0",
  "request_id": "turn-or-request-id",
  "gate": "search",
  "decision": {
    "value": "no_search",
    "probability_search": 0.0
  },
  "decision_source": "rule",
  "reason": "local_file_or_repo",
  "backend": "rule",
  "latency_ms": 0.0,
  "confidence": 1.0,
  "metadata": {}
}
```

`confidence` is optional because not every future Gate must expose it. `metadata`
is the only intentionally open extension point. Unknown top-level contract fields
or unknown Gate decision fields are rejected by the reference validator.

Current Gate-specific decision payloads are:

```text
search:
  value = search | no_search
  probability_search

model_tier:
  value = fast | strong
  difficulty_score
  probability_strong

notification:
  value = silent | digest | notify_now
  notify_now
  priority_score
```

There is intentionally no `reasoning_effort`, provider/model identifier, or Web
tool name here.

## 6. Turn Context and lifecycle

The portable Turn Context is deliberately minimal:

```text
platform
session_id?
turn_id?
step?
task?
capabilities[]?
```

Not every platform has the same identity model, so these fields are correlation
inputs rather than a demand for identical lifecycle code. Hermes may use a string
turn id while DSH uses session + numeric turn identity.

The following are **not** default Turn Context fields:

- full/raw transcript;
- system prompt;
- auth headers or credentials;
- native platform request/session objects.

Adapters may send the bounded task/event required by a Gate to the configured
Runtime endpoint, but raw content is not part of persistent contract telemetry.

## 7. Gate Configuration

The portable configuration vocabulary is:

```text
enabled: boolean
mode: off | shadow | canary
timeout_ms: positive integer
```

Current product configuration remains backward compatible. Existing per-gate
switches and Canary feature switches remain adapter configuration; Phase 7B does
not replace either platform's install/config format.

## 8. Action Outcome

A decision and a platform action are separate records. The shared outcome status is:

| Status | Meaning |
|---|---|
| `observed` | decision was recorded; no active change was made |
| `applied` | Adapter safely applied a verified platform mapping |
| `skipped` | Adapter intentionally took no action, e.g. Shadow or an unmet local precondition |
| `failed_open` | an error occurred and native platform behavior was preserved |
| `unsupported` | valid decision, but this Adapter/provider/model has no verified active mapping |

`reason` / `action_reason` should be stable machine-readable strings such as:

```text
notification_shadow_only
no_active_authority
canary_not_acknowledged
unsupported_provider_or_model
original_reasoning_not_high
runtime_timeout
runtime_http_error
malformed_response
mutation_exception
```

An unsupported mapping is a valid outcome, not a Runtime failure.

## 9. Canary authority

The core invariant is:

```text
decision != permission
```

Active behavior follows this sequence:

```text
Runtime decision
      |
      v
Adapter eligibility
      |
      v
platform policy / compatibility
      |
      v
verified mutation or no-op outcome
```

The current Adapters additionally require explicit Canary acknowledgement and only
grant active authority to audited deterministic rule decisions. Model-probability
recommendations remain observation-only.

## 10. Fail-open contract

For adapter/runtime integration, fail-open has one precise meaning:

> **The original platform behavior is preserved.**

This applies to:

- timeout;
- HTTP/network error;
- malformed or incomplete Runtime response;
- unsupported schema/version;
- hook/lifecycle failure at the integration boundary;
- unsupported provider or model;
- mutation exception.

Failures are isolated per Gate when possible. A broken Model Tier call must not
erase a separately valid Search decision. Platform mutation code is also guarded:
if a copy/filter/rewrite fails, the original request/tool behavior survives.

The Adapter records `failed_open` for actual errors. A known-but-unimplemented
provider mapping records `unsupported` instead.

## 11. Unified observation schema

The comparable fields are:

```text
adapter_contract_version
platform
adapter_version
gate
mode
decision
decision_source
reason
backend
latency_ms
action_status
action_reason
request_id
```

Adapters may add privacy-safe metadata such as event character count, tool name,
provider/model identifier, or before/after request knobs when that is useful for
debugging a platform mapping. Such fields are telemetry extensions, not decision
semantics.

Never persist through this schema:

- API keys / credentials;
- auth headers;
- raw system prompts;
- full transcripts.

Raw task/event text follows the existing privacy-safe policy: it may be sent to the
configured Runtime because the Gate needs an input, but it is not stored in normal
Adapter observation records.

## 12. Hermes mapping

Hermes v0.7.0 keeps native Hermes behavior and lifecycle code:

| Decision | Current Adapter mapping |
|---|---|
| `Search=no_search` + audited deterministic reason | acknowledged Canary may hide exact `web_search` / `web_extract` entries |
| `ModelTier=fast` + audited deterministic reason | optional verified mapping may change the first supported request from high to low reasoning effort |
| `Notification=*` | Shadow observation only |

Hermes-specific tool names, provider request fields, profile state, and middleware
remain outside the common contract.

## 13. DeepSeek Harness mapping

DSH v0.4.0 keeps DSH-specific hooks and provider request types:

| Decision | Current Adapter mapping |
|---|---|
| `Search=no_search` + audited deterministic reason | acknowledged Canary may deny exact verified public-Web tools |
| `ModelTier=fast` + audited deterministic reason | optional verified provider/model routes may change first-call `reasoningEffort` from high to low |
| `Notification=*` | Shadow observation only |

Provider/model allowlists and DSH tool names remain Adapter policy, not Runtime
contract fields.

## 14. Adding a third Adapter

A new Claude Code, Codex, OpenCode, Pi, or other Adapter should:

1. keep existing Runtime Gate semantics unchanged;
2. normalize Runtime responses into Adapter Contract v1;
3. provide only the minimum Turn Context needed by that platform;
4. implement platform mappings locally;
5. treat Runtime decisions as advisory until local Canary authority is proven;
6. preserve native behavior on every integration failure;
7. emit the common observation fields without persisting private prompt content;
8. add platform-specific fields only as metadata/extensions;
9. prove lifecycle cleanup and rollback with real platform tests before advertising Active support.

Do not add a new common abstraction merely because one platform has a feature.
Promote a concept into the shared contract only after multiple real adapters need
the same semantic concept.

With v1, a future Gate can be implemented in this order:

```text
Runtime defines Gate semantics
        ->
Contract exposes the semantic decision
        ->
Hermes maps it locally
        ->
DSH maps it locally
        ->
future adapters choose their own safe mapping
```

That is the intended boundary: one decision language, multiple platform-native
execution strategies.
