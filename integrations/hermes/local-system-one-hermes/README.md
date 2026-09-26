# Local System One for Hermes

A reversible **System One / Laya Typed Decisions control layer for Hermes Agent**.

Use it when you want Hermes to make small, frequent routing decisions locally before the main LLM call, without replacing Hermes' normal provider or turning a small model into an all-powerful router.

Typical decisions include:

- whether a task needs public/current Web information;
- whether a bounded task is eligible for a lower reasoning tier;
- which decisions should remain observation-only until enough evidence exists.

The plugin talks to a separate Local System One service over loopback HTTP. It is deliberately conservative: first install is **OFF**, Shadow changes nothing, Canary requires explicit acknowledgement, and any Local System One failure leaves the original Hermes request unchanged.

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
- records privacy-safe operational metadata;
- **does not rewrite the Hermes provider request**.

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

## Safe defaults

| Setting | Default |
|---|---|
| `mode` | `off` |
| `search_gate_enabled` | `true` |
| `model_tier_gate_enabled` | `true` |
| `canary_acknowledged` | `false` |
| `canary_web_filter_enabled` | `true` |
| `canary_reasoning_downgrade_enabled` | `false` |
| `timeout_ms` | `500` |

Hermes exposes these settings through the plugin settings UI.

## Fail-open behavior

Local System One is advisory infrastructure, not a dependency Hermes must survive.

If the sidecar is unavailable, times out, or returns an incomplete recommendation:

- the plugin does not apply Canary mutations;
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
- names of tools changed by Canary.

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
- **model-probability Active routing:** not supported

For architecture, benchmark evidence and the Laya/ANE runtime, see the main project:

https://github.com/NMTZ-z/system-one-benchmark-lab
