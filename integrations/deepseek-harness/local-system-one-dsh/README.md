# local-system-one-dsh

[![powered by dsh](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square)](https://github.com/deepseek-ai/deepseek-harness)

Native DeepSeek Harness adapter for Local System One **Search Gate + Model Tier Gate + Notification Gate + Completion Gate**.

Version `0.5.0` implements **Adapter Contract v1** while keeping installation inert by default, observing all four gates, preserving the audited Search Canary, and keeping Model Tier Canary explicitly opt-in. Completion is Shadow-only and never stops or restarts the DSH loop.

## Compatibility

Phase 7A revalidated two exact DSH versions:

| DSH | Commit | Validation |
|---|---|---|
| `dsh-v0.1.7-rc.2` / `0.1.7-rc.2` | `477b4f420553e8a52c2fbccc464d7561b239c443` | full Search + Model Tier lifecycle, successful provider E2E before the later Nova route degradation |
| `dsh-v0.2.1-alpha.1` / `0.2.1-alpha.1` | `5badb15009ae1756c3afe0ae0cef1faafc290ccc` | Search + Model Tier + Notification lifecycle verified; full provider completion and high/low/tool-loop Model Tier E2E passed through StepFun Step Plan / `step-5-preview` |

Node.js: `>=22.19.0`. Validation host: Apple Silicon arm64.

The package intentionally declares an exact optional peer fence:

```text
0.1.7-rc.2 || 0.2.1-alpha.1
```

Do not replace it with an unbounded range. DSH remains prerelease software, and each new version should be wire-probed before widening the fence.

## Architecture

```text
DeepSeek Harness
       |
       v
local-system-one-dsh
       |
       | HTTP
       v
Local System One Runtime
       |
       +-- Search Gate
       +-- Model Tier Gate
       +-- Notification Gate
       +-- Completion Gate
       +-- Rules / typed model / MLX / ANE
```

The adapter is an HTTP client. It does not import Laya, MLX, Core ML, Torch, or the Python runtime.

## Adapter Contract v1

The Runtime owns abstract decision semantics such as `Search=no_search` and
`ModelTier=fast`. This adapter owns DSH hooks, session/turn state, exact tool-name
mapping, provider/model compatibility, request mutation, Canary authority, and
rollback. `reasoningEffort` is therefore a DSH mapping detail, not a Local System
One decision field.

Contract observations use a shared status vocabulary:

```text
observed | applied | skipped | failed_open | unsupported
```

They also include `adapter_contract_version=1.0`, `platform=deepseek_harness`,
adapter version, Gate, mode, semantic decision, reason/backend/latency, action
status/reason, and request ID. Raw task/event text is not written into these logs.

See [`docs/ADAPTER_CONTRACT.md`](../../../docs/ADAPTER_CONTRACT.md) and the
machine-readable schema at
[`contracts/adapter-contract-v1.schema.json`](../../../contracts/adapter-contract-v1.schema.json).

## Modes and safe defaults

| Setting | Default |
|---|---|
| `mode` | `off` |
| `search_gate_enabled` | `true` |
| `model_tier_gate_enabled` | `true` |
| `notification_gate_enabled` | `true` |
| `completion_gate_enabled` | `true` |
| `completion_loop_probe_enabled` | `false` |
| `canary_acknowledged` | `false` |
| `canary_web_filter_enabled` | `true` |
| `canary_reasoning_downgrade_enabled` | `false` |
| `timeout_ms` | `500` |

- `off`: no Local System One request and no DSH mutation.
- `shadow`: Search Gate and Model Tier Gate are evaluated on step 1; Notification Gate and Completion Gate observe the final turn at `turn/end`. The four gates can be enabled independently. DSH behavior is never changed.
- `canary`: Shadow behavior plus narrowly audited mutations. Canary requires `canary_acknowledged: true`; otherwise it degrades to Shadow.

Example:

```yaml
mode: shadow
service_url: http://127.0.0.1:8787
timeout_ms: 500
search_gate_enabled: true
model_tier_gate_enabled: true
notification_gate_enabled: true
completion_gate_enabled: true
canary_acknowledged: false
canary_web_filter_enabled: true
canary_reasoning_downgrade_enabled: false
```

The adapter sends only the current user task plus an ephemeral request ID to the configured Local System One endpoint. It does not send the full transcript or system prompt.

## Phase 8B optional loop probe

An opt-in `completion_loop_probe_enabled: true` enables a one-per-turn
**Shadow-only** observation on the native `session/event:tool/result` event,
without awaiting model inference in the event handler. It is independent of,
and additional to, the existing `turn/end` Completion observation. The
observation uses generic progress wording, not raw tool output. It does not
mutate DSH control flow and is **off by default**. Turn and session state
is scoped and cleared on lifecycle boundaries; failures are fail-open.

Only the pinned upstream DSH lifecycle and simulated event replay plus real
HTTP adapter integration were evaluated. Full native LLM-backed Agent
E2E and a production-quality task dataset remain outstanding. [Phase 8B
report](../../../docs/PHASE8B_FINAL_REPORT.md): **Active NO-GO**.

## Search Gate

Endpoint:

```text
POST /v1/workflows/search-gate
```

Audited deterministic hard no-Web reasons:

- `bounded_transform_task`
- `local_file_or_repo`
- `connected_app_data`

Verified public-Web tool names:

- `web_search`
- `web_fetch`
- `mcp__tavily__tavily_search`

Search Canary may deny one of those exact tools only when all of the following hold: effective mode is Canary, Search Gate is enabled, the Web-filter feature switch is enabled, the decision is `no_search`, `decision_source=rule`, `backend=rule`, and the reason is in the audited set.

Model probability never receives active deny authority. Generic shell, local-file, browser, or arbitrary MCP tools are not treated as public-Web tools merely because they could reach a network indirectly.

## Model Tier Gate

Endpoint:

```text
POST /v1/workflows/model-tier-gate
```

Shadow stores privacy-safe metadata only: tier, decision source, reason, difficulty score, probability, confidence, backend, latency, request ID, and observation timestamp. Raw task text is not stored in adapter state.

The runtime owns the abstract decision (`fast` / `strong`). The DSH adapter owns the platform-specific mapping. Phase 7A deliberately does **not** make `reasoning_effort` part of a universal adapter contract.

### Experimental Canary mapping

Disabled by default.

When all safety conditions are met, Phase 7A may copy the first DSH provider-call config and change only:

```text
reasoningEffort: high -> low
```

Current active route allowlist:

```text
nova/deepseek-v4-flash
stepfun/step-5-preview
```

`stepfun/step-5-preview` was wire-probed on DSH `0.2.1-alpha.1`: native `high` and native `low` both completed successfully, the real provider JSON carried `reasoning_effort=high/low`, and Local System One Canary automatically changed a deterministic bounded transform from high to low. A tool-loop probe then verified first call `low` followed by subsequent tool-result calls back at `high`.

Current audited deterministic hard-fast reasons:

- `bounded_transform`
- `bounded_structured_transform`

Active mutation additionally requires effective Canary mode, explicit acknowledgement, Model Tier enabled, `canary_reasoning_downgrade_enabled: true`, a deterministic rule result (`decision_source=rule`, `backend=rule`), `tier=fast`, an audited reason, an exact verified provider/model pair, and an original `reasoningEffort` of `high`.

The mutation is copy-on-write and local to the first provider call of the turn. Tool-loop step 2 was verified to return to the original `high` request setting. Any uncertainty or exception fails open to the untouched provider config.

The exact model ID `deepseek-v4.1-flash` is **not** in the active allowlist: the current Nova token plan returned `403 model is not available in the current token plan`, so it has not earned an active compatibility claim.

## Notification Gate

Endpoint:

```text
POST /v1/workflows/notification-gate
```

Notification remains **Shadow-only** in `0.5.0`. DSH observes the last visible `assistant/message` for the turn and, at `turn/end`, submits that bounded event plus lifecycle metadata to Local System One. The `session/event` contract is observe-only, so this work cannot veto or delay the main Agent turn.

The adapter logs only decision metadata (`delivery`, `notify_now`, source, reason, score, confidence, backend, latency and event length). It never logs the final response text. No push, webhook, message or other delivery action is taken even if Local System One returns `notify_now`.

A real three-gate E2E on DSH `0.2.1-alpha.1` observed all three HTTP calls in one completed StepFun turn: `/search-gate`, `/model-tier-gate`, and `/notification-gate`.

## Completion Gate

Endpoint:

```text
POST /v1/workflows/completion-gate
```

Completion is **Shadow-only** in `0.5.0`. The adapter captures the bounded task on
the first `agent/pre-step`, observes the latest `assistant/message`, counts
`tool/result` failures, and submits one compact Completion request at `turn/end`.
It clears the ephemeral record at turn/session cleanup.

The semantic result is `complete`, `continue`, or `verify`. DSH receives no stop,
retry, or tool-suppression mutation from this Gate. Telemetry records only
decision metadata and task/result character counts, never the raw text. Dead or
malformed Runtime responses fail open to native DSH behavior.

The first public 120-case benchmark recorded zero premature completions but also
zero complete recall under the current conservative threshold. Active stop is
therefore explicitly **NO-GO** for Phase 8A. See
[`docs/COMPLETION_GATE.md`](../../../docs/COMPLETION_GATE.md).

## Turn scope and privacy

DSH invokes `agent/pre-step` again after tool results, so Search and Model Tier are evaluated only for `step === 1`. Notification and Completion are evaluated once at turn end after the final assistant event is known.

Search and Model Tier decisions are kept separately under session + turn identity. Completion uses bounded ephemeral session + turn state and is cleared at `turn/end`; `session/end` / `session/close` clears remaining state. No raw task, final response, transcript, system prompt, credentials, or tool arguments are emitted by adapter logs. Search/Model Tier send the current task to the configured service; Notification sends the bounded final event; Completion sends the bounded task/result plus structured execution counters. A remote `service_url` therefore carries those inputs off-device.

## Fail-open behavior

Each gate is independent. A timeout, HTTP error, malformed response, or dead Local System One service on one gate does not suppress the other gate and does not break the DSH turn.

Canary mutations also fail open: if authority cannot be proven or a mutation throws, the original tool/provider behavior is preserved. Known but unverified provider/model mappings are recorded as `unsupported`; actual integration failures are recorded as `failed_open`.

## Community bundle install

Install into a supported `headless` profile:

```bash
dsh plugin --profile headless add github:NMTZ-z/system-one-benchmark-lab#dsh-plugin
```

The bundle installs in `off` mode. Enabling Shadow or Canary requires an explicit profile override.

Example Shadow override:

```yaml
- id: local-system-one-dsh
  config:
    mode: shadow
    service_url: http://127.0.0.1:8787
    timeout_ms: 500
    search_gate_enabled: true
    model_tier_gate_enabled: true
    canary_acknowledged: false
    canary_web_filter_enabled: true
    canary_reasoning_downgrade_enabled: false
```

A Cordis patch replaces the targeted row's complete `config`, so retain every field you depend on when overriding defaults.

Remove the bundle with:

```bash
dsh plugin --profile headless remove local-system-one-dsh
```

If DSH reports an incompatible-version refusal after an upgrade, do not grant a blanket exemption. Revalidate the new DSH version and widen the exact peer fence only after the lifecycle and provider-wire probe passes.

## Build and test from source

```bash
cd integrations/deepseek-harness/local-system-one-dsh
npm install
npm run typecheck
npm test
npm run build
npm audit
```

The package is not published to npm. The `dsh-plugin` distribution branch carries built output so GitHub installation does not depend on install-time compilation.

## Local development load

Build the package, copy `example/cordis.patch.yml`, and replace its `file://` path with the absolute path to `dist/index.js`.

Then launch a supported DSH checkout:

```bash
dsh --profile headless --patch /path/to/local-system-one-dsh.patch.yml "your task"
```

Provider credentials remain outside Git. Validation used existing Hermes-managed Nova and StepFun credentials without printing or storing either credential value. The successful Phase 7B provider path was `DSH -> StepFun Step Plan -> step-5-preview`.

## Rollback

Rollback remains ordered and reversible:

```text
Canary
  -> Shadow
  -> Off
  -> disable patch/plugin entry
  -> remove adapter
```

Removing the adapter restores native DSH behavior without reinstalling DSH or changing other profiles/providers.

## Phase reports

See [PHASE7A_MODEL_TIER_PARITY.md](PHASE7A_MODEL_TIER_PARITY.md) for Model Tier parity and [PHASE7B_NOTIFICATION_STEPFUN.md](PHASE7B_NOTIFICATION_STEPFUN.md) for the earlier Notification Shadow + StepFun provider-wire validation. The latter filename is retained as historical evidence; the current project-level **Phase 7B** is the Unified Adapter Contract documented in [`docs/ADAPTER_CONTRACT.md`](../../../docs/ADAPTER_CONTRACT.md).

## Still out of scope

Phase 8A does not add Active notification delivery, Active Completion stopping, Retry Gate, Action Risk Gate, cross-provider routing, global/profile model mutation, probability-threshold active routing, or custom agent loops.
