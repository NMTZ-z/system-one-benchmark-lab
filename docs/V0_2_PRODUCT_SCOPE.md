# Local System One v0.2.0 — frozen product scope

This is the **target contract**, not a claim that current main already meets it.
Release versions, actual commits and pending provenance are tracked in the
[release manifest](../release/v0.2.0-manifest.json).

## Required release behavior

| Capability | v0.2.0 requirement | Default / authority |
|---|---|---|
| Runtime | Install and run local Laya 421M / MLX on supported Apple Silicon; show health and pinned model identity. | MLX default. ANE optional and health-gated, with verified artifact provenance. |
| Five existing Gates | Preserve Search, Model Tier, Notification, Completion, Retry / Escalation and their contracts. | First Hermes Shadow observes Search only. Each other Gate requires a separate explicit opt-in; Completion and Retry remain advisory. |
| Hermes plugin | Install in a named isolated profile; doctor, start, Shadow, status, OFF, stop and uninstall; preserve unrelated Hermes configuration and native behavior. | OFF on installation. Shadow does not mutate Agent requests or actions. No production Active/Canary authorization. |
| HTTP and MCP | HTTP exposes the five Gate contracts and health; MCP delivers corresponding five Gate tools and health by 8.4C. | No MCP deployment or persistent background service without opt-in. |
| DSH | Ship a built, version-matched adapter for the exact supported DSH versions in the release manifest; validate advertised features on each. | OFF on installation; opt-in Shadow. Existing historical Canary code does not grant release-time production authority. |
| Lifecycle | Show effective status and bounded decision records; fail open to native Agent behavior; OFF stops new observations; stop and uninstall are safe and reversible. | User controls all transitions; do not kill unrelated processes or delete unrelated data. |

**First-use policy**

```text
Runtime: Local Laya / MLX
Hermes: OFF by default
First Shadow: Search Gate only
Other Gates: explicit opt-in
Active: NOT_AUTHORIZED
Cloud Decision Provider: disabled
Persistent Service: opt-in
```

Changing from OFF to Shadow must not silently turn on every observation path.
Previously explicit per-Gate choices may be preserved and shown to the user;
first-use defaults enable only Search. Current `0.9.0` has four enabled Gate
settings, so 8.4B must implement and test this requirement.

## Network and data

The sidecar defaults to `http://127.0.0.1:8787`. The Agent's own Provider
traffic is separate from the Local System One sidecar. A Gate can send bounded
task, response or failure context to the configured sidecar; the product must
show the effective destination and data categories before enabling observation.
A non-loopback destination requires explicit informed user action and must not
be chosen silently or reached via an unnoticed redirect. Model acquisition is a
separate, disclosed download of the pinned model, never task-content upload.
Decision records and diagnostics must avoid raw prompts, results and secrets by
default. Transport and authentication for any remote sidecar must be designed
and tested before advertising remote use.

## Deferred beyond this release

H4E repair/execution, Action Risk Gate, Memory Gate, Capability Router,
multi-Agent delegation, automatic model hot-switching, real-tool automatic
retry, automatic Agent termination, automatic paid-model escalation, a new
complex safety framework, a Web Dashboard and additional Agent-platform
adapters are outside v0.2.0. They may be considered for v0.2.1/v0.3 only
after a separate decision; no version is promised here.

OpenAI Luna Decisions API is optional research in 8.4C. It cannot be a
dependency or automatic fallback for local usage. The existing Jev research
backend likewise is not enabled in the product runtime.

## Delivery sequence

1. **8.4A:** verified main, archive index, version plan, release manifest
   specification, documentation and 8.4B handoff.
2. **8.4B:** Hermes First-Run MVP, Search-only Shadow and full reversible
   lifecycle; publish `v0.2.0-rc.1` only after its own checks.
3. **8.4C:** HTTP/MCP parity and installable DSH compatibility; optional Luna
   research; publish `v0.2.0-rc.2` after its own checks.
4. **8.4D:** separately authorized Owner Shadow use, final `v0.2.0` release
   and a reviewed Hermes Catalog update request.

Offline or synthetic results cannot establish user value, saved costs, actual
Provider billing, or production authorization.
