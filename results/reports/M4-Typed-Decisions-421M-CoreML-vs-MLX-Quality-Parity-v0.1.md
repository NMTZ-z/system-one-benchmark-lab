# M4 Typed Decisions 421M — Core ML vs MLX Quality Parity v0.1

Date: 2026-09-23

## Scope

This is a same-checkpoint, same-dataset backend comparison.

Both runs use the pinned Laya Typed Decisions 421M checkpoint semantics on the
same 400-case / 2,000-decision public Typed Decisions test split:

- dataset: `LocalLLaMA/typed-decisions`
- dataset revision:
  `c76749ec58bd8c3d2ea706b31c333a9059c38f90`
- source checkpoint:
  `convaiinnovations/laya-typed-decisions`
- source revision:
  `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`

Compared backends:

- MLX FP16
- Core ML ordinary SDPA export, CPU+GPU

This is a **backend parity test**, unlike the published 322M multilingual ANE
bundle, which is a different checkpoint.

## Decision-by-decision parity

All 400 cases completed on both backends.

| Parity check | Result |
|---|---:|
| Decisions compared | 2,000 |
| Selected-answer mismatches | **0** |
| Cases with a selected-answer mismatch | **0** |
| Exact full answer objects | 109 / 2,000 |
| Max probability absolute delta | **0.0030** |
| Max Score-value absolute delta | **0.0039** |
| Max Noul absolute delta | **0.0049** |
| Max confidence absolute delta | **0.0049** |
| Max action-probability absolute delta | **0** |

The low count of byte-for-byte/equality-level answer objects is caused by small
numeric differences in probabilities, scores, and confidence fields. It does
not represent decision disagreement: **all 2,000 selected decisions are the
same**.

## Aggregate quality metrics

| Metric | Core ML CPU+GPU | MLX FP16 | Core ML − MLX |
|---|---:|---:|---:|
| Accuracy | **0.766000** | **0.766000** | **0** |
| Soft accuracy | 0.47064096 | 0.47063611 | +0.00000485 |
| KL from gold | 0.11704566 | 0.11704294 | +0.00000272 |
| Total variation | 0.17406198 | 0.17405921 | +0.00000277 |
| Brier vs soft gold | 0.06147308 | 0.06147329 | −0.00000022 |
| ECE, 15 bins | 0.21327178 | 0.21328331 | −0.00001153 |
| Score MAE | 0.24239109 | 0.24241814 | −0.00002704 |
| Within 1 score level | **0.995** | **0.995** | **0** |

These deltas are negligible for model-quality interpretation. The ordinary Core
ML export therefore preserves the MLX quality result on the full public task,
not only on the smaller conversion-fidelity case set.

## End-to-end case latency

The quality runner supplies all five questions for each case. Model loading is
excluded from per-case latency, but first-use shape specialization inside the
run is not separately removed.

| Metric | Core ML CPU+GPU | MLX FP16 | Core ML / MLX |
|---|---:|---:|---:|
| Model load | 18.945 s | 1.152 s | **16.44×** |
| Mean / case | 1938.5 ms | 830.0 ms | **2.34×** |
| P50 / case | 887.9 ms | 513.7 ms | **1.73×** |
| P95 / case | 5341.7 ms | 2838.6 ms | 1.88× |
| P99 / case | 6667.2 ms | 5337.7 ms | 1.25× |
| Max / case | 11439.8 ms | 8250.6 ms | 1.39× |

This quality workload is not the same as the warmed short-decision microbenchmark
from Phase 2. It contains heterogeneous prompt lengths and five questions per
case. The ordinary Core ML B1 export processes questions sequentially, while
MLX uses batching.

Therefore these numbers describe **shipped end-to-end case behavior**, not an
equal-tensor batching experiment.

## Latency by workflow

P50:

| Workflow | Core ML | MLX | Core ML / MLX |
|---|---:|---:|---:|
| agent_trace_observability | 297.3 ms | 277.4 ms | 1.07× |
| customer_service | 2561.0 ms | 814.0 ms | **3.15×** |
| invoice_processing | 860.4 ms | 581.9 ms | 1.48× |
| security_incidents | 542.5 ms | 499.1 ms | 1.09× |

The per-workflow spread reinforces that a single overall latency number is not a
universal property of the backend. Input length, Core ML shape specialization,
and MLX batching all matter.

The very high Core ML workflow means are also affected by first-use shape
specialization. For steady short-input runtime, use the warmed Phase 2
microbenchmark instead of these first-pass workflow means.

## Phase decision

**Phase 3D: PASS.**

Verified on the complete public test set:

1. Core ML and MLX cover all 2,000 decisions.
2. Selected decisions are **2,000 / 2,000 identical**.
3. Aggregate quality metrics are effectively unchanged.
4. The ordinary Core ML backend is materially slower for this five-question
   end-to-end workload on the base M4, despite preserving quality.
5. Backend-performance conclusions must remain separate from model-quality
   conclusions.

The practical runtime choice for the current 421M checkpoint on this machine is
therefore workload-dependent, with MLX particularly advantaged when several
questions can be batched.

## Files

Core ML raw run:

- `results/raw/m4-typed-decisions-quality-coreml.json`

MLX raw run:

- `results/raw/m4-typed-decisions-quality-mlx.json`

Decision-by-decision comparison:

- `results/processed/m4-typed-decisions-quality-coreml-vs-mlx.json`

Comparator:

- `benchmarks/quality/compare_backends.py`