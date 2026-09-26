# Hermes Model Tier Paired Benchmark — 32 Pairs v1.1

Date: 2026-09-25
Status: Phase 6.1 calibration result

## Question

For bounded low-risk Hermes tasks, does `gemini-3.8-flash-tiered` with `reasoning_effort=low` preserve task quality while materially improving latency versus `reasoning_effort=high`?

## Method

- Hermes profile: `systemoneeval`
- provider: `local-gemini`
- model: `gemini-3.8-flash-tiered`
- efforts: low vs high
- toolset: `clarify`
- Local System One plugin: OFF during latency benchmark
- 32 paired tasks / 64 real Hermes calls
- pair order: seeded/counterbalanced
- quality scoring: deterministic validators, no LLM judge
- categories: JSON transform, sort/dedupe, date normalization, field extraction, CSV→JSON, formatting, bounded summary, constrained rewrite

The first benchmark version exposed a validator-design flaw in the rewrite category: the prompt allowed models to emit recommended alternatives, while the validator counted the whole response against the requested character limit. Both tiers produced semantically correct rewrites but were marked failed. The four rewrite prompts were corrected to require exactly one final sentence and were rerun as v1.1. No other category was changed.

## Quality

Final v1.1 result:

- low: 32/32 PASS
- high: 32/32 PASS
- both pass: 32/32
- low-only quality regression: 0
- high-only quality regression: 0

For this bounded task set, low preserved measured task correctness.

## Latency

Hermes turn latency:

- low mean: 7.110 s
- high mean: 7.068 s
- low median: 5.817 s
- high median: 6.392 s
- mean paired high-minus-low difference: -0.042 s
- median paired high-minus-low difference: -0.168 s
- low faster: 15/32 pairs
- high faster: 17/32 pairs

Bootstrap 95% CI for the mean paired high-minus-low difference:

- [-0.941 s, +0.833 s]

Median pairwise high/low latency ratio:

- 0.972

Bootstrap 95% CI:

- [0.889, 1.165]

Interpretation:

> The earlier 7-pair signal that low was materially faster did **not** reproduce on the 32-pair set. The current data does not demonstrate a reliable latency benefit for low reasoning on this local-gemini route.

Latency also shows substantial per-request variance. Some categories favor low in this small sample, others favor high. The category samples are only four tasks each and should not be used for routing policy.

## Token/accounting observations

Hermes reports `reasoning_tokens=0` for this route and has no usable provider cost estimate (`cost_status=unknown`). Input/cache accounting also varies with cache state, so total-token comparisons are not reliable cost evidence.

Observed output tokens:

- low mean: 520.7
- high mean: 543.8
- mean difference: high used 23.2 more output tokens
- low used fewer output tokens in 19/32 pairs
- high used fewer output tokens in 13/32 pairs

This is a small signal, not sufficient evidence of material cost savings. It must not be presented as a reasoning-token or monetary-cost reduction.

## System One control overhead

The pure low/high benchmark intentionally ran with the Local System One plugin OFF.

A reproducible 96-run control-overhead benchmark (32 tasks × 3 repetitions, Search Gate + Model Tier Gate sequentially) measured:

- 96/96 successful;
- mean: 65.6 ms;
- median: 57.2 ms;
- P95: 113.0 ms;
- hard-fast deterministic rule rate: 75%.

Only 24/32 task pairs are actually eligible for the current hard-fast allowlist. On those 24 pairs:

- quality: 24/24 PASS for low and high;
- low faster: 13/24;
- high faster: 11/24;
- raw mean high-minus-low: +0.212 s;
- after subtracting mean control overhead: +0.146 s in favor of controlled-low;
- net bootstrap 95% CI: -1.027 s to +1.245 s.

So the eligible subset shows a **weak positive latency signal**, but the uncertainty interval is far too wide to claim a reliable speedup.

## Product decision

The Model Tier hard-fast mechanism is technically correct and reversible:

- it can mutate only the current provider request from high→low;
- model-based recommendations do not mutate requests;
- dead Local System One fails open to high;
- production profiles remain unchanged.

However, Phase 6.1 changes the product conclusion:

> **Do not promote hard-fast reasoning downgrade to a production default on the claim that it reliably makes Hermes faster.**

Keep it experimental/Canary until one of the following is demonstrated:

1. a provider exposes reliable reasoning-token/cost savings for low;
2. repeated paired measurements on another provider/model show a stable latency advantage;
3. real workload economics show a meaningful resource/throughput benefit despite similar single-turn latency.

The strongest validated value of Local System One currently remains the control-plane architecture and deterministic policy enforcement, not proven speed gains from same-model reasoning downgrade on local-gemini.