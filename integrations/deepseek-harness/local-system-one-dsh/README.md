# local-system-one-dsh

[![powered by dsh](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square)](https://github.com/deepseek-ai/deepseek-harness)

Native DeepSeek Harness adapter for Local System One **Search Gate + Model Tier Gate**.

Version `0.2.0` keeps installation inert by default, observes both gates independently in Shadow mode, preserves the existing audited Search Canary, and adds an explicitly opt-in experimental Model Tier Canary for one verified Nova / DeepSeek route.

## Compatibility

Phase 7A revalidated two exact DSH versions:

| DSH | Commit | Validation |
|---|---|---|
| `dsh-v0.1.7-rc.2` / `0.1.7-rc.2` | `477b4f420553e8a52c2fbccc464d7561b239c443` | full Search + Model Tier lifecycle, successful provider E2E before the later Nova route degradation |
| `dsh-v0.2.1-alpha.1` / `0.2.1-alpha.1` | `5badb15009ae1756c3afe0ae0cef1faafc290ccc` | plugin load, lifecycle hooks, Model Tier decision path, and provider-wire mutation verified; final provider completion currently blocked by the same Nova route error reproduced on rc2 |

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
       +-- Rules / typed model / MLX / ANE
```

The adapter is an HTTP client. It does not import Laya, MLX, Core ML, Torch, or the Python runtime.

## Modes and safe defaults

| Setting | Default |
|---|---|
| `mode` | `off` |
| `search_gate_enabled` | `true` |
| `model_tier_gate_enabled` | `true` |
| `canary_acknowledged` | `false` |
| `canary_web_filter_enabled` | `true` |
| `canary_reasoning_downgrade_enabled` | `false` |
| `timeout_ms` | `500` |

- `off`: no Local System One request and no DSH mutation.
- `shadow`: Search Gate and Model Tier Gate may be enabled independently. Both are evaluated once on step 1 of each user turn. DSH behavior is never changed.
- `canary`: Shadow behavior plus narrowly audited mutations. Canary requires `canary_acknowledged: true`; otherwise it degrades to Shadow.

Example:

```yaml
mode: shadow
service_url: http://127.0.0.1:8787
timeout_ms: 500
search_gate_enabled: true
model_tier_gate_enabled: true
canary_acknowledged: false
canary_web_filter_enabled: true
canary_reasoning_downgrade_enabled: false
```

The adapter sends only the current user task plus an ephemeral request ID to the configured Local System One endpoint. It does not send the full transcript or system prompt.

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
```

Current audited deterministic hard-fast reasons:

- `bounded_transform`
- `bounded_structured_transform`

Active mutation additionally requires effective Canary mode, explicit acknowledgement, Model Tier enabled, `canary_reasoning_downgrade_enabled: true`, a deterministic rule result (`decision_source=rule`, `backend=rule`), `tier=fast`, an audited reason, an exact verified provider/model pair, and an original `reasoningEffort` of `high`.

The mutation is copy-on-write and local to the first provider call of the turn. Tool-loop step 2 was verified to return to the original `high` request setting. Any uncertainty or exception fails open to the untouched provider config.

The exact model ID `deepseek-v4.1-flash` is **not** in the active allowlist: the current Nova token plan returned `403 model is not available in the current token plan`, so it has not earned an active compatibility claim.

## Turn scope and privacy

DSH invokes `agent/pre-step` again after tool results, so both gates are evaluated only for `step === 1`.

Search and Model Tier decisions are kept separately under session + turn identity. `turn/end` deletes both. `session/end` / `session/close` clears remaining session state. No raw task, transcript, system prompt, credentials, or tool arguments are stored in adapter state or emitted by adapter logs.

## Fail-open behavior

Each gate is independent. A timeout, HTTP error, malformed response, or dead Local System One service on one gate does not suppress the other gate and does not break the DSH turn.

Canary mutations also fail open: if authority cannot be proven, the original tool/provider behavior is preserved.

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

Provider credentials remain outside Git. Validation used the existing Nova provider configuration without printing or storing the credential value.

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

## Phase 7A report

See [PHASE7A_MODEL_TIER_PARITY.md](PHASE7A_MODEL_TIER_PARITY.md) for the wire probe, parity matrix, provider-state caveat, Unified Adapter Contract notes, and GO/NO-GO decision.

## Still out of scope

Phase 7A does not add Completion Gate, Retry Gate, Action Risk Gate, Notification Gate, cross-provider routing, global/profile model mutation, probability-threshold active routing, or custom agent loops.
