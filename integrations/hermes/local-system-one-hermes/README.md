# Local System One for Hermes

A reversible **System One / Laya Typed Decisions control layer for Hermes Agent**.

Use it when you want Hermes to make small, frequent routing decisions locally before the main LLM call, without replacing Hermes' normal provider or turning a small model into an all-powerful router.

Typical decisions include:

- whether a task needs public/current Web information;
- whether a bounded task is eligible for a lower reasoning tier;
- whether a completed Agent turn should stay silent, join a digest, or merit an immediate notification;
- whether the completed turn appears complete, should continue, or needs verification before any future stop authority could be considered;
- which decisions should remain observation-only until enough evidence exists.

The plugin talks to a separate Local System One service over loopback HTTP. It is deliberately conservative: first install is **OFF**, Shadow changes nothing, Canary requires explicit acknowledgement, and any Local System One failure leaves the original Hermes request unchanged.

Hermes adapter `0.8.0` implements **Adapter Contract v1**. The Runtime owns abstract
decisions such as `Search=no_search` and `ModelTier=fast`; this plugin owns the
Hermes-specific lifecycle, tool/provider mapping, Canary authority, rollback, and
fail-open behavior. Platform details such as `reasoning_effort` and exact Hermes
tool names are intentionally not part of the Runtime contract. See
[`docs/ADAPTER_CONTRACT.md`](../../../docs/ADAPTER_CONTRACT.md).

## Before you install

You need:

- Hermes Agent `>=0.21.4`;
- macOS / Apple Silicon for the validated Local System One runtime;
- a running Local System One service, normally at `http://127.0.0.1:8787`.

The Local System One runtime lives in the same public repository:

```bash
git clone https://github.com/NMTZ-z/system-one-benchmark-lab.git
cd system-one-benchmark-lab

python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
local-system-one --host 127.0.0.1 --port 8787
```

Check it before enabling the plugin:

```bash
curl http://127.0.0.1:8787/health
```

For the optional Apple Neural Engine backend, see the repository root README.

## Install

### Hermes Plugin Catalog

Once this plugin is listed in the official Hermes Plugin Catalog:

```bash
hermes plugins install local-system-one-hermes
```

Catalog installs are pinned to the exact commit reviewed by Hermes maintainers.

### Direct Git install

Before catalog admission, or when deliberately installing a custom revision:

```bash
hermes plugins install \
  NMTZ-z/system-one-benchmark-lab/integrations/hermes/local-system-one-hermes
```

Hermes treats direct Git installs as custom/unreviewed sources. For reproducibility, pin a full commit SHA with `--ref`.

The repository also contains helper scripts for profile-aware installation and rollback:

```bash
scripts/install_hermes_system_one_plugin.sh systemoneeval
scripts/hermes_system_one_status.sh systemoneeval
```

## Recommended first run: Shadow

Start with a disposable or evaluation profile:

```bash
scripts/set_hermes_system_one_mode.sh systemoneeval shadow
```

Shadow mode:

- calls the enabled Local System One gates;
- observes Search and Model Tier before the provider request;
- observes Notification after the final Agent response and turn lifecycle are known;
- observes Completion once at the session boundary using bounded task/result state;
- records privacy-safe operational metadata;
- **does not rewrite the Hermes provider request or send notifications**.

This is the recommended way to evaluate the plugin before allowing any request mutation.

## Modes

| Mode | Local System One calls | Changes Hermes provider request? | Recommended use |
|---|---:|---:|---|
| `off` | No | No | Default / fully inert |
| `shadow` | Yes | **No** | Evaluation and calibration |
| `canary` | Yes | Only narrow audited rules | Explicit experiments |

### Off

No Local System One HTTP calls and no Hermes request changes.

```bash
scripts/set_hermes_system_one_mode.sh systemoneeval off
```

### Shadow

Observe recommendations without changing the provider request.

```bash
scripts/set_hermes_system_one_mode.sh systemoneeval shadow
```

### Canary

Canary can mutate a provider request, so entering it requires explicit acknowledgement:

```bash
scripts/set_hermes_system_one_mode.sh systemoneeval canary --ack-canary
```

Leaving Canary for `shadow` or `off` automatically revokes the acknowledgement.

If `mode=canary` is set without acknowledgement, the plugin degrades to Shadow behavior instead of mutating requests.

## What Canary is allowed to do

Canary only acts on audited **deterministic rules**. Model-probability recommendations remain observation-only.

### Public-Web filter

For audited hard no-Web rules, acknowledged Canary may hide only the directly advertised Hermes tools:

- `web_search`
- `web_extract`

It does **not** disable terminal access, browser tooling, MCP/connectors, local files, or indirect network paths. It is not a network sandbox.

### Reasoning downgrade

Disabled by default.

If you explicitly enable `canary_reasoning_downgrade_enabled`, audited hard-fast rules may change one first provider request from:

```text
reasoning_effort=high -> reasoning_effort=low
```

for `gemini-3.8-flash-tiered`.

This remains experimental. A 32-pair Hermes benchmark preserved measured task quality but did **not** establish a reliable latency improvement, so the public plugin does not enable or advertise this as a guaranteed optimization.

## Notification Gate (Shadow only)

Version `0.8.0` retains Notification Gate observation through Hermes' real `post_llm_call` and `on_session_end` hooks. The final assistant response is held only in bounded process-local memory until the turn ends, sent to the configured Local System One endpoint for classification, then discarded.

The persisted plugin state contains only metadata such as `delivery`, `notify_now`, reason, score, confidence, backend, latency and the event character count. The response text itself is not persisted.

Notification has **no Active authority** in this release. A `notify_now` decision is evidence for evaluation only; the plugin does not send a push, message, webhook or other user-visible notification. Failed turns may set `blocking_failure=true` so the runtime can exercise its deterministic failure rule, but the result remains observation-only.

A live `systemoneeval` Hermes smoke on this release produced all three gate decisions and a Notification result of `digest` from the ANE backend without changing delivery behavior.

## Completion Gate (Shadow only)

Version `0.8.0` adds Completion observation without granting stop authority. The
plugin captures a bounded task at `pre_llm_call`, bounded final result at
`post_llm_call`, tool/failure counts through `post_tool_call`, and evaluates once
at the real `on_session_end` boundary.

The Runtime returns `complete`, `continue`, or `verify`. The plugin only records
the semantic result. It never terminates the Hermes loop, suppresses a tool call,
skips verification, or emits a final answer.

Raw task/result text lives only in bounded process-local state until the session
boundary. Persisted Completion telemetry contains decision metadata and character
counts, not the text itself. If the Runtime is unavailable, the observation is
recorded as `failed_open` and native Hermes behavior continues unchanged.

The first 120-case benchmark produced a `0.00%` premature-completion rate but also
`0.00` complete recall under the current conservative threshold. That is useful
Shadow evidence, not evidence for Active stopping. See
[`docs/COMPLETION_GATE.md`](../../../docs/COMPLETION_GATE.md).

## Safe defaults

| Setting | Default |
|---|---|
| `mode` | `off` |
| `search_gate_enabled` | `true` |
| `model_tier_gate_enabled` | `true` |
| `notification_gate_enabled` | `true` |
| `completion_gate_enabled` | `true` |
| `canary_acknowledged` | `false` |
| `canary_web_filter_enabled` | `true` |
| `canary_reasoning_downgrade_enabled` | `false` |
| `timeout_ms` | `500` |

Hermes exposes these settings through the plugin settings UI.

## Fail-open behavior

Local System One is advisory infrastructure, not a dependency Hermes must survive.

If the sidecar is unavailable, times out, or returns an incomplete recommendation:

- the affected Gate does not receive Canary authority;
- a healthy independent Gate can still be observed or applied under its own safety checks;
- any mutation exception restores the original Hermes request;
- Hermes keeps its original provider request;
- the main Hermes turn continues.

This behavior has been tested with deliberate dead-service fault injection.

## Privacy

Raw task text is not written into plugin state.

Shadow/Canary state stores only operational metadata such as:

- request IDs;
- decision source / route reason;
- probabilities or scores;
- backend and latency;
- names of tools changed by Canary;
- Notification delivery/reason/score/confidence and event length, never the final response text.
- Completion decision/reason/confidence and task/result lengths, never the task or final response text.

Search/Model Tier send the current task to the configured Local System One endpoint. Notification sends the final Agent event text plus lifecycle metadata. With the default loopback service this remains local; pointing `service_url` at a remote host sends those inputs to that remote service.

The Local System One service also avoids persisting raw request payloads by default.

## Rollback / uninstall

Return to Shadow or OFF at any time:

```bash
scripts/set_hermes_system_one_mode.sh systemoneeval shadow
scripts/set_hermes_system_one_mode.sh systemoneeval off
```

Full removal:

```bash
scripts/uninstall_hermes_system_one_plugin.sh systemoneeval
```

Uninstall removes this plugin's configuration and state while leaving Hermes, other plugins, models, sessions and agent files alone.

## Verification

From the repository root:

```bash
python -m pytest -q \
  tests/test_adapter_contract.py \
  tests/test_hermes_system_one_plugin.py \
  tests/test_hermes_system_one_scripts.py

hermes plugins validate integrations/hermes/local-system-one-hermes
hermes plugins doctor integrations/hermes/local-system-one-hermes --ci
```

A disposable live lifecycle smoke test is also included:

```bash
scripts/smoke_hermes_system_one_live.sh systemoneeval
```

It exercises OFF, Shadow, acknowledged Canary, fail-open behavior and restoration.

## Current release posture

- **OFF:** safe default and fully inert
- **Shadow:** recommended evaluation mode
- **hard no-Web Canary:** narrow, evidence-backed experiment
- **reasoning downgrade Canary:** experimental and disabled by default
- **Notification Gate:** Shadow-only; `silent` / `digest` / `notify_now` are observed but never delivered by the plugin
- **Completion Gate:** Shadow-only; `complete` / `continue` / `verify` are observed but never terminate Hermes
- **model-probability Active routing:** not supported

For architecture, benchmark evidence and the Laya/ANE runtime, see the main project:

https://github.com/NMTZ-z/system-one-benchmark-lab
