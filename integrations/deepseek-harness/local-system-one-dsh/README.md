# local-system-one-dsh

Native DeepSeek Harness adapter for the Local System One Search Gate.

Phase 1 is intentionally narrow: it decides whether a turn needs generic public Web access, observes the decision in Shadow mode, and can deny a small audited set of Web/Search tools in explicitly acknowledged Canary mode.

## Compatibility

The first validated target is pinned to:

- DeepSeek Harness: `dsh-v0.1.7-rc.2`
- DeepSeek Harness commit: `477b4f420553e8a52c2fbccc464d7561b239c443`
- Node.js: `>=22.19.0`
- Apple Silicon validation host: arm64

DeepSeek Harness is still a Developer Preview. Do not replace the pinned target with an unbounded `main` checkout when reproducing these results.

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
       +-- Rules
       +-- Laya policy
       +-- MLX / ANE
```

The adapter is only an HTTP client. It does not import Laya, MLX, Core ML, Torch, or any Python runtime.

## Modes

- `off`: no Local System One request and no tool mutation.
- `shadow`: one Search Gate request on step 1 of each user turn; tools are never mutated.
- `canary`: Shadow behavior plus deny authority for audited deterministic hard no-Web rules only.

Canary additionally requires:

```yaml
canary_acknowledged: true
```

If `mode: canary` is configured without acknowledgement, the adapter deliberately degrades to Shadow.

## Configuration

```yaml
mode: shadow
service_url: http://127.0.0.1:8787
timeout_ms: 500
search_gate_enabled: true
canary_acknowledged: false
```

The configured service receives:

```json
{
  "task": "<current user task>",
  "request_id": "<ephemeral UUID>"
}
```

The adapter never sends the full conversation transcript or system prompt.

## Search Gate endpoint

The adapter calls:

```text
POST /v1/workflows/search-gate
```

A valid response contains at least:

```text
decision
decision_source
reason
probability_search
backend
latency_ms
request_id
```

Any connection error, timeout, HTTP error, or malformed response is fail-open.

## Canary authority

A Web/Search call can be denied only when all of the following are true:

1. effective mode is Canary;
2. the tool name is in the verified public-Web allowlist;
3. Search Gate returns `decision=no_search`;
4. `decision_source=rule`;
5. `backend=rule`;
6. the reason is one of the audited hard no-Web reasons.

Audited reasons:

- `bounded_transform_task`
- `local_file_or_repo`
- `connected_app_data`

Raw Laya/model probability never has active deny authority.

The Phase 0 verified public-Web tool names are:

- `web_search`
- `web_fetch`
- `mcp__tavily__tavily_search`

This is intentionally an exact allowlist. Generic tools such as `bash`, local file tools, and arbitrary MCP tools are not blocked merely because they could indirectly reach a network.

## Turn scope

DeepSeek Harness invokes `agent/pre-step` again after tool results. The adapter therefore evaluates Search Gate only for `step === 1`.

Decisions are stored only in memory under session + turn identity. `turn/end` deletes the decision, preventing a previous turn from influencing a later one.

No raw task, message list, system prompt, or transcript is stored in adapter state or adapter logs.

## Build and test

```bash
cd integrations/deepseek-harness/local-system-one-dsh
npm install
npm run typecheck
npm test
npm run build
```

The package is private in Phase 1 and is not published to npm.

## Load into DeepSeek Harness

Build the adapter, copy `example/cordis.patch.yml`, and replace its `file://` path with the absolute path to `dist/index.js`.

Then launch a pinned DeepSeek Harness checkout with the patch:

```bash
dsh --profile headless --patch /path/to/local-system-one-dsh.patch.yml "your task"
```

Provider configuration remains separate from this adapter. For the validated Nova setup, keep credentials outside Git and use placeholders such as:

```text
${NOVA_API_KEY}
${NOVA_BASE_URL}
${NOVA_MODEL}
```

## Privacy

Shadow and Canary send the current task to the configured Local System One endpoint.

The default endpoint is loopback (`127.0.0.1`). If `service_url` is changed to a remote address, the current task is sent to that remote service. Do not describe a remote configuration as "fully local."

Metadata logs contain decision fields only and intentionally omit task text.

## Rollback

Rollback is ordered and reversible:

```text
Canary
  -> Shadow
  -> Off
  -> disable patch/plugin entry
  -> remove adapter
```

Removing the adapter does not require reinstalling DeepSeek Harness. With the plugin absent, native DSH behavior is restored.

## Out of scope for Phase 1

This adapter does not implement Model Tier routing, Notification Gate, provider/model rewriting, reasoning-effort rewriting, custom agent loops, LLM stream mutation, or embedded Python runtimes.
