# M4 Laya ANE W8 × Typed Decisions Capacity Audit v0.1

Date: 2026-09-23

## Scope

This audit asks a deliberately narrow question:

> Can the published Laya multilingual ANE W8 bundle represent the public
> `LocalLLaMA/typed-decisions` test decisions **without changing or truncating
> the benchmark input**?

The answer is **no for the published L96 bundle**.

This is a capacity audit, not a model-quality score.

## Fixed artifacts

Published ANE bundle:

- repository: `aac6fef/laya-multilingual-coreml-ane-w8`
- source checkpoint: `convaiinnovations/laya-multilingual`
- source revision:
  `052592a15d198d9ad47da779604259b10b47b7aa`
- precision: FP16 compute graph with W8 k-means compressed selected convolution weights
- shape: **B1 / L96 / K32**
- maximum context length: **96 tokens**
- maximum options: 32

Benchmark:

- repository: `LocalLLaMA/typed-decisions`
- pinned revision:
  `c76749ec58bd8c3d2ea706b31c333a9059c38f90`
- split: `all/test`
- 400 cases
- 2,000 decisions

The audit uses the ANE bundle's own tokenizer, RL configuration, and upstream
prompt-construction logic. It does **not** load the Core ML model, because model
execution is irrelevant to input-capacity analysis.

## Result

| Metric | Result |
|---|---:|
| Supported decisions at L96 | **0 / 2,000** |
| Capacity coverage | **0.0%** |
| Over-capacity decisions | **2,000 / 2,000** |
| Minimum prompt length | **127 tokens** |
| Median prompt length | **323 tokens** |
| P95 prompt length | **450 tokens** |
| P99 prompt length | **575 tokens** |
| Maximum prompt length | **631 tokens** |
| Option-count range | 2–5 |

Every workflow and every question type is completely over the published L96
capacity:

- agent trace observability: 0 / 500 supported
- customer service: 0 / 500 supported
- invoice processing: 0 / 500 supported
- security incidents: 0 / 500 supported
- Choice: 0 / 600 supported
- Noul: 0 / 600 supported
- Score: 0 / 800 supported

The limitation is therefore context length, not the K32 option limit.

## Context-length coverage curve

Using the **same unmodified prompts** and tokenizer, hypothetical fixed context
limits would cover:

| Max length | Supported | Coverage |
|---:|---:|---:|
| 96 | 0 | 0.00% |
| 128 | 3 | 0.15% |
| 160 | 110 | 5.50% |
| 192 | 472 | 23.60% |
| 256 | 622 | 31.10% |
| 384 | 1,597 | 79.85% |
| 512 | 1,961 | 98.05% |
| 640 | 2,000 | 100.00% |

This table is **not** a performance forecast for future ANE exports. It only
states how much of the current benchmark would fit if an otherwise compatible
bundle existed at each maximum sequence length.

## Why no ANE quality score is reported

Producing a score by truncating these prompts would change the task. The
benchmark explicitly treats question instructions and criteria descriptions as
part of the input; dropping state or question tokens can alter the intended
decision.

Therefore the published L96 ANE bundle receives:

- **capacity coverage: 0%**
- **quality score: not applicable on this benchmark**

Over-capacity decisions are **not counted as wrong predictions**. They are
reported separately as unsupported inputs.

## Interpretation boundary

This does **not** mean the published ANE model is defective. It was exported for
a fixed L96 workload and already has a valid short-decision latency/energy
baseline on this M4.

It means only that the current public ANE artifact and the public
Typed Decisions quality benchmark operate at incompatible input lengths.

It also does not establish that an L384/L512/L640 ANE export is practical,
fast, or memory-efficient. Longer fixed shapes materially change attention
cost, compile behavior, memory use, and potentially ANE placement. Those would
require a separate engineering experiment.

Finally, this ANE bundle is based on the **322M multilingual checkpoint**, while
the Phase 3A quality baseline uses the **421M Typed Decisions specialist**.
Even a future longer-context multilingual ANE result would remain a
model-capacity/quality comparison, not a pure backend A/B against the 421M
checkpoint.

## Files

Reproducible audit:

- `benchmarks/quality/ane_capacity.py`

Raw result:

- `results/raw/m4-laya-ane-w8-typed-decisions-capacity.json`

Processed summary:

- `results/processed/m4-laya-ane-w8-typed-decisions-capacity-summary.json`