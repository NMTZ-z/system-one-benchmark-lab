# Phase 3 Interim — Jev / Laya / Published ANE Evaluation v0.1

Date: 2026-09-23

## What is independently measured here

### Laya Typed Decisions 421M specialist — M4 MLX FP16

Public Typed Decisions test split, 400 cases / 2,000 decisions:

- coverage: 100%
- accuracy: **0.7660**
- soft accuracy: 0.47064
- KL from gold: 0.11704
- Brier: 0.06147
- ECE: 0.21328
- Score MAE: 0.24242
- P50 end-to-end case latency: 513.7 ms

### Same 421M checkpoint — M4 Core ML CPU+GPU

- selected decisions vs MLX: **2,000 / 2,000 identical**
- accuracy: **0.7660**
- max probability delta vs MLX: 0.0030
- P50 end-to-end case latency: 887.9 ms

Conclusion: ordinary Core ML preserves full-task quality, while MLX is faster
for this five-question-per-case workload.

### Published 322M multilingual ANE W8 — M4

Short-decision runtime baseline:

- ANE W8: 4.598 ms sustained short-decision interval
- 3.213× faster than the compiled MLX short-decision baseline in the frozen
  Phase 1 energy run
- substantially lower gross system energy per decision in that workload

Typed Decisions quality-benchmark capacity:

- fixed shape: B1 / L96 / K32
- benchmark prompt lengths: 127–631 tokens
- supported unmodified decisions: **0 / 2,000**

Therefore no valid Typed Decisions quality score is assigned to the published
L96 ANE bundle. Truncating benchmark inputs would change the task.

## What is externally referenced, not locally rerun

The public Typed Decisions dataset card reports TypeSafe **Jev 1.13.0** as a
general zero-shot model:

| Metric | Jev 1.13.0 external |
|---|---:|
| Accuracy | 0.727 |
| Soft accuracy | 0.580 |
| KL from gold | 1.442 |
| Brier | 0.148 |
| ECE | 0.144 |
| Score MAE | 0.391 |
| Within 1 level | 0.952 |
| P50 / case | 710 ms |

The source says this was measured on 2026-09-18 over all 400 cases / 2,000
decisions with zero errors.

This column remains explicitly marked **external** until the local runner is
given TypeSafe API credentials.

## The comparison that is valid now

The data supports three separate statements:

1. **Backend parity:** the 421M ordinary Core ML conversion preserves the 421M
   MLX model's decisions and quality metrics.
2. **Runtime specialization:** the published 322M ANE L96 graph is extremely
   fast on the short-decision workload it was exported for, but its fixed
   context is too short for the public Typed Decisions quality benchmark.
3. **Training-regime distinction:** the 421M Typed Decisions checkpoint is a
   specialist trained on this benchmark's workflow family; Jev is reported as a
   zero-shot generalist. Their aggregate quality numbers must not be interpreted
   as an overall intelligence ranking.

## What remains

Phase 3B local Jev rerun:

- authenticate with a TypeSafe API key through `TYPESAFE_API_KEY`
- call `GET /v1/models` and verify the pinned `jev-1.13.0` is available
- run all 400 cases
- record the concrete `model` returned by every response
- score with the same local metrics code
- compare against both the external Jev reference and local Laya results

No benchmark code changes are required for that run.
