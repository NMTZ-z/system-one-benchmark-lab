# Model Tier Gate v0.2 — Hard-Fast Canary

Date: 2026-09-25
Status: model-based routing Shadow-only; isolated hard-fast mechanism PASS, broad production latency gate NO-GO

## Goal

Choose whether an agent task needs the baseline/strong reasoning tier or can safely use a cheaper/faster reasoning tier.

The gate is not a global model ranking. It is a control-plane decision made **before** expensive generative reasoning.

## Endpoint

`POST /v1/workflows/model-tier-gate`

Important response fields:

- `tier`: fast / strong
- `decision_source`: rule / model
- `reason`
- `difficulty_score`
- `probability_strong`
- backend / route metadata

## Safety ordering

Hard-strong policy always wins before any fast rule.

Hard strong is returned when:

- risk is high or critical;
- the action is irreversible;
- the caller explicitly requires high precision.

These are consequence-of-error policies, not intelligence judgments.

## Deterministic hard-fast policy

The first active experiment deliberately recognizes only **bounded, low-risk tasks with explicit source material**.

Current hard-fast reasons:

- `bounded_transform`
- `bounded_structured_transform`

### bounded_transform

Examples:

- rewrite supplied text;
- proofread supplied text;
- translate supplied text;
- shorten/compress supplied text.

The source material must be present either in structured context or visibly embedded in the current task. An instruction such as "translate this" without the actual content does not qualify.

### bounded_structured_transform

Examples with explicit input data:

- deduplicate/sort a supplied list;
- normalize supplied dates;
- extract named fields from supplied text;
- convert supplied CSV/data to JSON.

The heuristics intentionally prefer false negatives over broad downgrade coverage.

## Model fallback

Everything outside hard policy becomes a 0–4 Score decision:

0. routine/direct;
1. light reasoning;
2. moderate reasoning;
3. complex reasoning;
4. expert-level deep reasoning.

The current research threshold for `strong` is expected score >= 2.0.

**Model-probability fast/strong decisions are not approved for Active routing.**

Task-description sensitivity was observed during calibration: operational wrapper wording can move the same semantic task across the threshold.

## Same-provider low/high paired calibration

A small isolated paired set used:

- provider: local-gemini
- model: `gemini-3.8-flash-tiered`
- same task/context/toolset
- reasoning effort: low vs high

Seven objective bounded tasks were completed successfully by both tiers:

- low: 7/7
- high: 7/7

Measured Hermes turn latency:

- low mean: 4.824 s
- high mean: 5.812 s
- low median: 4.351 s
- high median: 5.224 s
- low faster: 5/7 pairs
- high faster: 2/7 pairs
- median high/low latency ratio: 1.235×

This is promising evidence for a narrow hard-fast path, not a general production benchmark.

## Verified Hermes wire shape

Hermes request dumps were used with non-sensitive sentinel tasks to verify the actual local-gemini wire format.

For `gemini-3.8-flash-tiered`:

- low request: top-level `reasoning_effort = low`
- high request: top-level `reasoning_effort = high`

No `extra_body.reasoning` field is used on this route.

The Canary therefore modifies only the top-level `reasoning_effort` of the current provider request.

## Isolated Hermes hard-fast Canary

Plugin version: `local-system-one-hermes v0.4.0`

Canary remains hard-blocked outside profile:

`systemoneeval`

The Model Tier mutation has additional gates:

1. complete Local System One recommendation must succeed;
2. tier decision must come from a deterministic rule;
3. reason must be an audited hard-fast reason;
4. provider request model must be exactly `gemini-3.8-flash-tiered`;
5. original provider request must explicitly contain `reasoning_effort = high`;
6. only the first provider call of the turn is eligible.

The plugin then copy-on-write changes only:

`high -> low`

It never persists a new profile reasoning setting.

## Real Canary results

Processed artifact:

`results/processed/hermes-model-tier-canary-v0.1.json`

### Bounded rewrite

Caller requested high.

Decision:

- tier: fast
- decision source: rule
- reason: bounded_transform

Final provider wire:

- model: `gemini-3.8-flash-tiered`
- reasoning effort: **low**

Hermes completed normally.

### Bounded structured transform

Task: deterministic deduplicate/sort transformation over supplied numbers.

Decision:

- tier: fast
- decision source: rule
- reason: bounded_structured_transform

Final provider wire:

- reasoning effort: **low**

The correct output was produced. Search Gate did not need a hard-rule action in this case, demonstrating that the two control paths operate independently.

### Model-probability fast control

A simple Python explanation received a model-based fast recommendation.

Final provider wire remained:

- reasoning effort: **high**

This is intentional: model-only fast recommendations remain Shadow-only.

### Dead-service fail-open

Local System One was deliberately pointed at an unused local port.

The bounded task would normally qualify for hard-fast routing, but the control decision failed.

Final provider wire remained:

- reasoning effort: **high**

Hermes completed normally.

Result: fail-open PASS.

## Interaction with Search Canary

Search and Model Tier actions are independent.

A bounded rewrite can simultaneously:

- remove directly advertised `web_search` / `web_extract` because of an audited Search hard rule;
- change tiered Gemini reasoning from high to low because of an audited Model Tier hard-fast rule.

A structured transform may trigger only the reasoning downgrade while leaving Web tools untouched.

## Current limitations

- Only one exact same-provider model route is authorized for the first Canary.
- No cross-provider routing is implemented.
- No persistent model switch is performed.
- Model-probability tier decisions remain Shadow-only.
- Seven low/high paired tasks are too few for production activation.
- Hard-fast pattern coverage is intentionally narrow.
- Cost accounting on the local-gemini route is incomplete, so current evidence is primarily quality + latency rather than monetary savings.

## Current decision

- deterministic hard-fast isolated Canary: PASS;
- model-based fast routing: NO-GO;
- production Hermes profiles: unchanged;
- evaluation profile: returned to Shadow after Canary.

The expanded 32-pair v1.1 set reached 32/32 quality parity for both low and high, but low was faster in 15/32 pairs and the paired latency confidence interval crossed zero. Including Local System One control overhead, broad hard-fast production activation is therefore NO-GO. Future work, if pursued, should target only field extraction, sort/deduplicate, and CSV→JSON, which showed exploratory positive latency signals at n=4 each.

## Phase 6.1 update — 32-pair benchmark

The initial seven-pair latency signal did not reproduce at larger scale.

A 32-pair / 64-call deterministic benchmark produced:

- low quality: 32/32 PASS;
- high quality: 32/32 PASS;
- low mean turn: 7.110 s;
- high mean turn: 7.068 s;
- low median turn: 5.817 s;
- high median turn: 6.392 s;
- low faster: 15/32;
- high faster: 17/32;
- paired mean difference bootstrap 95% CI: -0.941 s to +0.833 s.

Therefore the project no longer treats same-provider high→low routing as a demonstrated latency optimization on `local-gemini`. The mechanism remains technically valid and reversible, but production activation needs evidence of real provider cost/reasoning-token savings or a repeatable performance benefit on another route.

Full report: `docs/HERMES_MODEL_TIER_PAIRED_32.md`.


### Hard-fast eligible subset

The current deterministic allowlist actually covers 24/32 benchmark tasks. On this product-relevant subset:

- low/high quality: 24/24 vs 24/24;
- low faster: 13/24;
- high faster: 11/24;
- raw mean high-minus-low latency: +0.212 s;
- mean Local System One control overhead: 65.6 ms;
- estimated net mean high-minus-controlled-low: +0.146 s;
- bootstrap 95% CI: -1.027 s to +1.245 s.

This is a weak positive signal, not reliable evidence of speedup. The hard-fast path remains isolated/experimental.