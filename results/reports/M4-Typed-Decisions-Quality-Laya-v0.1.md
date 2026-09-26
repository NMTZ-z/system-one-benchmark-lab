# M4 Typed Decisions Quality — Laya 421M v0.1

Date: 2026-09-23

## Scope

This is the Phase 3A quality baseline for the public
`LocalLLaMA/typed-decisions` test split.

- dataset revision: `c76749ec58bd8c3d2ea706b31c333a9059c38f90`
- 400 cases
- 2,000 typed decisions
- 5 questions per case
- workflows: agent trace observability, customer service, invoice processing,
  security incidents
- runtime: Laya Typed Decisions 421M, MLX FP16
- source revision:
  `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`

This checkpoint is a **specialist** trained for the typed-decisions task family.
It must not be described as a directly comparable zero-shot generalist to Jev
without keeping that training-regime difference explicit.

## Result

All 400 cases and all 2,000 decisions completed successfully.

| Metric | M4 measured |
|---|---:|
| Coverage | **100%** |
| Accuracy | **0.7660** |
| Soft accuracy | **0.47064** |
| KL from gold | **0.11704** |
| Total variation | **0.17406** |
| Brier vs soft gold | **0.06147** |
| ECE, 15 bins | **0.21328** |
| Mean confidence | 0.55272 |
| Score MAE | **0.24242** |
| Within 1 score level | **0.9950** |

The accuracy, soft-accuracy, Brier, ECE and score-MAE values reproduce the
published Laya specialist benchmark row to normal rounding precision. This is
also a cross-check that the local scorer is using the intended benchmark
semantics rather than merely producing plausible-looking numbers.

## By workflow

| Workflow | Accuracy | Soft acc | KL | Brier | ECE | Score MAE |
|---|---:|---:|---:|---:|---:|---:|
| agent_trace_observability | 0.730 | 0.4142 | 0.1001 | 0.0569 | 0.2294 | 0.2101 |
| customer_service | 0.764 | 0.4685 | 0.1564 | 0.0790 | 0.2128 | 0.2199 |
| invoice_processing | **0.804** | **0.5736** | 0.1279 | 0.0640 | **0.1650** | 0.2919 |
| security_incidents | 0.766 | 0.4263 | **0.0837** | **0.0460** | 0.2489 | 0.2478 |

A single aggregate accuracy hides substantial workflow differences. The
benchmark report should therefore retain these four rows in future Jev/Laya
comparisons.

## By decision type

| Type | Decisions | Accuracy | Soft acc | KL | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|
| Choice | 600 | 0.7333 | 0.3986 | 0.1736 | 0.0821 | 0.2549 |
| Noul | 600 | **0.8567** | **0.6187** | **0.0706** | **0.0494** | **0.1921** |
| Score | 800 | 0.7225 | 0.4136 | 0.1095 | 0.0550 | 0.1987 |

Score-only metrics:

- score MAE: 0.24242
- within one level: 0.995

## End-to-end case latency

The quality runner makes one public `predict` call per benchmark case, with all
five questions supplied together. Model loading is excluded from per-case
latency.

| Metric | M4 MLX |
|---|---:|
| Model load | 1.152 s |
| Mean / case | 830.0 ms |
| P50 / case | **513.7 ms** |
| P95 / case | 2838.6 ms |
| P99 / case | 5337.7 ms |
| Min / max | 222.9 / 8250.6 ms |
| Total benchmark execution | 416.0 s |

The large P95/P99 spread is real workload heterogeneity, not a reason to replace
the distribution with the easier short-decision microbenchmark. The four
workflows contain materially different state lengths and question schemas.

The run processed 582,370 input tokens and generated zero output tokens.

## Interpretation boundary

This result answers:

> How well does the specialist Laya Typed Decisions 421M checkpoint reproduce
> the public benchmark's soft decision targets on this M4 runtime?

It does **not** by itself answer:

- whether Laya is a better general-purpose System One model than Jev;
- whether MLX is the best backend for every workload;
- what 322M multilingual ANE quality would be on this full test;
- whether a 421M ANE graph would preserve this quality.

Jev 1.13.0 is evaluated as a zero-shot generalist. Any future head-to-head must
keep the specialist/generalist distinction visible next to the scores.

## Files

Raw run:

- `results/raw/m4-typed-decisions-quality-mlx.json`

Processed summary:

- `results/processed/m4-typed-decisions-quality-mlx-summary.json`

Runner:

- `benchmarks/quality/run_typed_decisions.py`

Metrics:

- `benchmarks/quality/metrics.py`