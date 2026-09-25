# local-system-one-hermes

A reversible Local System One control-plane plugin for Hermes Agent.

The plugin does **not** replace Hermes' normal LLM. It runs a local decision layer before the provider request and can observe or, in explicitly acknowledged Canary mode, apply a very small set of audited deterministic policies.

## Requirements

- Hermes Agent `>=0.21.4`
- Local System One HTTP service, normally at `http://127.0.0.1:8787`

If Local System One is unavailable, the plugin fails open and Hermes keeps its original provider request.

## Safe defaults

First install is intentionally inert:

| Setting | Default |
|---|---|
| `mode` | `off` |
| `search_gate_enabled` | `true` |
| `model_tier_gate_enabled` | `true` |
| `canary_acknowledged` | `false` |
| `canary_web_filter_enabled` | `true` |
| `canary_reasoning_downgrade_enabled` | `false` |
| `timeout_ms` | `500` |

Hermes exposes these fields through the plugin settings UI because they are declared in `plugin.yaml`.

## Install

From a Local System One checkout, default Hermes profile:

```bash
scripts/install_hermes_system_one_plugin.sh
```

Named profile:

```bash
scripts/install_hermes_system_one_plugin.sh sisi
```

A first install enables the plugin code but leaves behavior mode `off`. Re-running the installer updates plugin code while preserving existing settings and enabled/disabled state.

## Modes

### Off

No Local System One HTTP calls and no Hermes request changes.

```bash
scripts/set_hermes_system_one_mode.sh off
# or
scripts/set_hermes_system_one_mode.sh sisi off
```

### Shadow

Calls enabled Local System One gates and records privacy-safe decision metadata. It never rewrites the provider request.

```bash
scripts/set_hermes_system_one_mode.sh shadow
# or
scripts/set_hermes_system_one_mode.sh sisi shadow
```

### Canary

Canary can mutate a provider request, so activation requires an explicit acknowledgement every time you enter Canary:

```bash
scripts/set_hermes_system_one_mode.sh canary --ack-canary
# or
scripts/set_hermes_system_one_mode.sh sisi canary --ack-canary
```

Leaving Canary for `shadow` or `off` automatically revokes the acknowledgement.

If `mode=canary` is set directly without acknowledgement, the plugin degrades to Shadow behavior (`shadow_canary_ack_required`) rather than mutating requests.

## What Canary can do

Canary only reacts to audited **deterministic rule** decisions. Model-probability recommendations remain Shadow-only.

### Public-Web filter

Enabled by default once acknowledged Canary is active.

For audited hard no-Web rules it may hide only the directly advertised Hermes tools:

- `web_search`
- `web_extract`

It does not disable local files, terminal, MCP/connectors, browser tooling, or indirect network capabilities.

### Reasoning downgrade

Disabled by default.

If you explicitly enable `canary_reasoning_downgrade_enabled`, audited hard-fast rules may change a single first provider request from `reasoning_effort=high` to `low` for `gemini-3.8-flash-tiered`.

This is experimental. A 32-pair Hermes benchmark preserved measured quality but did **not** prove a reliable latency speedup, so public releases must not enable it by default or advertise it as guaranteed performance optimization.

## Independent gates

Search Gate and Model Tier Gate can be disabled independently in Hermes plugin settings:

- `search_gate_enabled`
- `model_tier_gate_enabled`

This lets users calibrate one control path without allowing latency or failure from the other path to participate in the decision.

## Status

```bash
scripts/hermes_system_one_status.sh
# or
scripts/hermes_system_one_status.sh sisi
```

The status command shows plugin/profile location, configured values versus manifest defaults, effective runtime safety state, and Local System One health.

## Uninstall / rollback

```bash
scripts/uninstall_hermes_system_one_plugin.sh
# or
scripts/uninstall_hermes_system_one_plugin.sh sisi
```

Uninstall performs the reversible cleanup path:

1. switches behavior off when possible;
2. disables and removes the Hermes plugin;
3. removes the plugin config entry;
4. removes Local System One plugin state metadata;
5. leaves Hermes, other plugins, models, sessions, and agent files alone.

## Privacy

Raw task text is not written into plugin state. Shadow/Canary state keeps only operational metadata such as request IDs, route reasons, probabilities/scores, latency, and names of tools changed by Canary.

Historical benchmark replay data used during development remains private and git-ignored.

## Current release posture

- Off: production-safe default
- Shadow: recommended evaluation mode
- hard no-Web Canary: isolated/experimental but evidence-backed
- reasoning downgrade Canary: experimental and disabled by default
- model-probability Active routing: not supported
