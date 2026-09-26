# Hermes Plugin Productization — v0.5.1

Date: 2026-09-25
Status: Phase 6.3 release-engineering checkpoint

## Objective

Turn the research integration `local-system-one-hermes` into a plugin another Hermes user can install, inspect, disable, upgrade and uninstall without editing source code or risking an irreversible Hermes configuration change.

## Product safety model

The plugin exposes three modes:

- `off`: no Local System One calls;
- `shadow`: decision observation only;
- `canary`: deterministic audited request mutation only after explicit acknowledgement.

Canary activation is portable across profiles but gated by `canary_acknowledged=true`.

A direct configuration mistake such as `mode=canary` without acknowledgement degrades to Shadow rather than mutating requests.

## Manifest and settings

The plugin manifest is now v2 and declares:

- `requires_hermes: >=0.21.4`;
- a Hermes `config_schema` for the Plugins settings surface;
- typed/default settings for mode, service URL, timeout, gate enablement and Canary switches.

Important default:

> `canary_reasoning_downgrade_enabled=false`

This matches the Phase 6.1 evidence: high→low was technically safe on the tested bounded set but did not demonstrate a statistically reliable latency advantage.

## Independent control paths

Search Gate and Model Tier Gate can now be observed independently.

This removes an unnecessary coupling discovered during Canary testing: a user evaluating Search should not have a Model Tier timeout invalidate the whole decision when Model Tier is intentionally disabled.

The fail-open invariant remains: every enabled control path required for the turn must complete successfully before a Canary mutation is eligible.

## Install and upgrade behavior

`scripts/install_hermes_system_one_plugin.sh`

- supports default and named profiles;
- validates source and installed plugin bytes with Hermes' validator;
- copies only publishable runtime files, never source bytecode/cache;
- first install enables plugin code but behavior defaults to off;
- upgrades replace plugin code while preserving existing settings and activation state;
- refuses to overwrite a non-matching plugin directory.

A real `systemoneeval` v0.4→v0.5 upgrade preserved the profile `config.yaml` SHA-256 exactly while updating plugin source/manifest bytes.

## Mode UX

`scripts/set_hermes_system_one_mode.sh`

Supports both default and named profile forms:

```text
set_hermes_system_one_mode.sh shadow
set_hermes_system_one_mode.sh <profile> shadow
```

Canary requires:

```text
set_hermes_system_one_mode.sh canary --ack-canary
```

or the named-profile equivalent.

Leaving Canary revokes acknowledgement automatically.

Hermes CLI YAML-coerces a bare `off` value to boolean false for plugin keys it does not know from core defaults. The product script therefore implements off by **unsetting** the mode key and relying on the manifest/plugin default string `"off"`. The manifest also quotes `"off"` explicitly so the settings UI exposes the enum correctly.

## Status UX

`scripts/hermes_system_one_status.sh`

Now supports default/named profiles and displays:

- profile and home path;
- installed plugin/version;
- configured settings, with missing values shown as manifest defaults;
- effective runtime safety state from plugin state;
- Local System One health.

## Uninstall / rollback

`scripts/uninstall_hermes_system_one_plugin.sh`

Performs idempotent cleanup:

- behavior off;
- Hermes plugin disable/remove;
- defensive plugin directory removal;
- plugin config entry removal;
- hashed plugin-data state directory removal.

It does not touch other Hermes plugins, models, agent files, sessions, or Local System One runtime deployment.

## Validation evidence

### Automated script/plugin tests

Productization-specific tests cover:

- default-profile install;
- named-profile install;
- upgrade preserving settings/activation;
- Canary requiring explicit acknowledgement;
- leaving Canary revoking acknowledgement;
- off using the manifest default instead of boolean false;
- clean uninstall of code/config/state;
- independent gate enablement;
- reasoning Canary feature switch.

### Real disposable Hermes profile lifecycle

A real temporary Hermes profile was used for:

1. fresh plugin install;
2. verification of safe off default;
3. Shadow transition;
4. return to off;
5. uninstall;
6. verification that plugin code, plugin config and plugin-data state were absent;
7. profile deletion.

PASS.

### Existing evaluation profile

`systemoneeval` was upgraded to v0.5.1 with its configuration hash unchanged, followed by a real Shadow one-shot:

- response: `OK`;
- Hermes call completed normally;
- effective plugin mode: `shadow`;
- Canary acknowledgement: false;
- Web Canary switch: true;
- reasoning downgrade switch: false;
- Local System One / ANE: healthy.

## Public-release handoff

On 2026-09-26 the project added a standard Python package definition plus an allowlisted public-release builder and sanitizer. A review bundle can now be generated without copying private replay data, model weights, raw Hermes logs, Core ML build outputs, or machine-specific experiment history.

The remaining publication gates are now narrower:

1. choose the public-project license and add `LICENSE` to the release allowlist and package metadata;
2. finish public-facing repository metadata/examples;
3. complete the final clean-machine model/runtime install smoke;
4. publish the reviewed repository/package through the chosen Git/catalog path.

Further control-policy expansion is not a prerequisite for the first public release.

## v0.5.1 real acceptance

The release-candidate plugin was revalidated after the local Hermes source updated to:

- Hermes Agent `0.21.5+2169.g5307e93`
- upstream `5307e932`

Real `systemoneeval` acceptance results:

- upgrade install preserved existing Shadow mode;
- Canary without `--ack-canary` was rejected with exit code 2 and mode stayed Shadow;
- full uninstall removed plugin code/config/state;
- Hermes still completed a one-shot turn after uninstall (`UNINSTALL_OK`);
- fresh install defaulted to OFF;
- OFF mode produced `OFF_ZERO_OK` with Local System One request delta `0`;
- Shadow produced `SHADOW_CALL_OK` with request delta `+2` (Search + Model Tier);
- acknowledged Canary could be entered explicitly;
- leaving Canary revoked acknowledgement automatically;
- experimental reasoning downgrade remained disabled by default;
- final evaluation state was restored to Shadow with acknowledgement false.

Six named production profile configs (`lili`, `sisi`, `susu`, `vivi`, `xixi`, `yaoyao`) remained byte-for-byte unchanged during the acceptance test.

The default Hermes config changed concurrently because the Hermes Desktop updater completed during the same window. It contains no `local-system-one-hermes` / `systemone` plugin entry, and the productization test did not restart production `hermes serve` / gateway processes.

Processed evidence:

`results/processed/hermes-plugin-productization-v0.5.1.json`

## Hermes 0.21.5/main post-upgrade regression

After the local Hermes installation moved to `0.21.5+2169.g5307e93` / upstream `5307e932`, the plugin was rechecked against the real `systemoneeval` profile:

- OFF completed a Hermes turn with zero new System One observations;
- Shadow recorded a successful deterministic decision without mutating the provider request;
- acknowledged Canary removed only `web_search` and `web_extract` on the first provider call for an audited bounded-transform rule;
- forcing the Runtime URL to `127.0.0.1:9` produced `URLError` in the decision layer while Hermes still completed normally, confirming fail-open behavior;
- the original Shadow configuration was restored afterward.

The repeatable check now lives in `scripts/smoke_hermes_system_one_live.sh` and refuses ordinary production-profile names unless explicitly overridden.