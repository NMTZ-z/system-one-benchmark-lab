# M4 Typed Decisions 421M Baseline v0.1

Date: 2026-09-23

## Executive summary

The published Laya Typed Decisions 421M Core ML bundle was independently
validated and benchmarked on the base Apple M4 Mac mini.

The Core ML CPU+GPU export passes the pinned upstream fidelity gate on this
machine: **63/63 selected answers agree**, maximum calibrated probability drift
is **0.00272663**, and **100/100 repeated API calls are stable**.

For short inputs, the best runtime depends on question count:

| Workload | Core ML CPU+GPU P50 | MLX FP16 P50 | Observation |
|---|---:|---:|---|
| 1 question | **33.715 ms** | 36.055 ms | Core ML 1.069× faster |
| 3 questions | 102.174 ms | **84.492 ms** | MLX 1.209× faster |
| 10 questions | 350.114 ms | **242.303 ms** | MLX 1.445× faster |
| 1 × 1024-token question | **304.921 ms** | 312.202 ms | near parity; Core ML 1.024× faster |

The crossover is explained by API/runtime behavior rather than a universal
backend advantage: the ordinary Core ML export executes multiple questions
sequentially, while the MLX reference uses batch size 16.

Allowing only CPU+Neural Engine does **not** make this ordinary export an ANE
model. Its one-question P50 rises to **1204.469 ms**, and the anticipated Core ML
plan prefers CPU for 1,643 nonconstant operations. Neural Engine appears only in
the supported-device set, not as the preferred device.

## Reproducibility anchors

- Core ML bundle: `aac6fef/laya-typed-decisions-coreml`
- Core ML Hub revision:
  `28d24fa8d67a3264556b23391ec6c3fd98573056`
- Source checkpoint: `convaiinnovations/laya-typed-decisions`
- Source revision:
  `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`
- Source weights SHA-256:
  `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e`
- Published Core ML package SHA-256:
  `517a8071290a29c2f1e19b38356fdc5c59dfdc801711a92606de6bba67596c85`
- Core ML shape: B1, enumerated L16–L1024, K32
- Precision: FP16
- Ordinary attention path: SDPA

## Independent M4 fidelity validation

The downloaded Hub bundle was revalidated against the pinned upstream FP32
reference rather than trusting the bundle's own release report.

| Metric | M4 result |
|---|---:|
| Selected-answer agreement | **63/63** |
| Max calibrated probability drift | **0.00272663** |
| Max action-probability drift | **0** |
| Repeat calls | 100 |
| Repeated rounded results identical | **yes** |
| Repeat-test elapsed time | 239.250 s |

This is conversion fidelity, not general task accuracy.

The checkpoint emits the upstream temperature-clamp warning for the
`choice:11+` bucket. Confidence affected by that bucket should therefore be
treated as uncalibrated; the warning does not invalidate selected-answer
agreement or the conversion-fidelity gate.

## Short-decision performance

Measurement boundary: complete synchronous `predict` call, including prompt
construction, tokenization, arrays, model execution, calibration, and result
formatting. Model loading and warmup are excluded.

Each primary short cell uses 10 warmup calls and 100 measured calls.

| Questions | Backend | P50 | P95 | Mean | Questions/s |
|---:|---|---:|---:|---:|---:|
| 1 | Core ML CPU+GPU | **33.715 ms** | 35.948 ms | 33.935 ms | 29.47 |
| 1 | MLX FP16 | 36.055 ms | 38.129 ms | 36.112 ms | 27.69 |
| 3 | Core ML CPU+GPU | 102.174 ms | 106.290 ms | 102.319 ms | 29.32 |
| 3 | MLX FP16 | **84.492 ms** | 87.856 ms | 84.596 ms | 35.46 |
| 10 | Core ML CPU+GPU | 350.114 ms | 369.038 ms | 350.843 ms | 28.50 |
| 10 | MLX FP16 | **242.303 ms** | 249.021 ms | 242.343 ms | 41.26 |

The 3- and 10-question rows compare shipped API behavior, not equal tensor
batching: Core ML runs questions sequentially while MLX batches them.

## 1024-token single-question performance

50 measured calls after 10 warmups:

| Backend | P50 | P95 | Mean |
|---|---:|---:|---:|
| Core ML CPU+GPU | **304.921 ms** | 311.638 ms | 305.063 ms |
| MLX FP16 | 312.202 ms | 319.886 ms | 313.204 ms |

At the full 1024-token input length, the two GPU routes are effectively close
on this machine, with a small Core ML advantage in this desktop run.

## Startup behavior

| Backend | Model load | First short prediction |
|---|---:|---:|
| Core ML CPU+GPU | 19.981 s | 3329.190 ms |
| MLX FP16 | **1.145 s** | **120.327 ms** |

These values are observed with existing OS/cache state, not a controlled
cold-boot study. They nevertheless show a large practical initialization cost
for the Core ML package.

For the 1024-token run, first prediction was 2520.961 ms for Core ML and
348.577 ms for MLX.

## Compute-plan evidence

### CPU+GPU

Anticipated preferred operation counts:

- `MLGPUComputeDevice`: **1,676**
- unknown/constant: 2,233

All 1,676 attributed nonconstant operations are supported on both CPU and GPU,
and the plan prefers GPU.

### CPU+Neural Engine

One-question result:

- P50: **1204.469 ms**
- P95: **1265.859 ms**
- about **35.7× slower** than the CPU+GPU P50

Anticipated preferred operation counts:

- `MLCPUComputeDevice`: **1,643**
- unknown/constant: 2,266
- `MLNeuralEngineComputeDevice`: **0 preferred**

The plan reports 1,228 operations as ANE-supported, but support is not the same
as placement. This is anticipated-plan evidence, not a runtime hardware trace.

## Comparison with upstream M3 Max results

The pinned upstream report measured the same Typed Decisions 421M ordinary
export on an M3 Max and reported much lower short-input latency. This should not
be interpreted as a clean M3-vs-M4 generation comparison: the M3 Max has a much
larger GPU and memory-bandwidth configuration, and software versions/cache state
also differ.

The useful observation is narrower: **on the base M4 Mac mini, the ordinary
421M GPU paths do not inherit the dramatic short-decision advantage seen from
the dedicated 322M ANE graph.**

## Phase gate decision

**Phase 2 — 421M runtime baseline: PASS.**

Verified:

1. The pinned public 421M Core ML bundle works on the M4 Mac mini.
2. Its conversion fidelity independently passes on this machine.
3. CPU+GPU and MLX FP16 short and L1024 baselines are frozen.
4. Ordinary CPU+NE selection does not provide useful ANE acceleration.
5. A dedicated ANE graph rewrite would be required for a meaningful 421M ANE
   experiment.

Next project step: **Phase 3 — unified decision-quality benchmark**, bringing
Jev, Laya Typed Decisions 421M, and the published 322M ANE path into one
evaluation framework while keeping model-quality and runtime-performance claims
separate.

Raw primary files:

- `results/raw/m4-typed-decisions-coreml-validation.json`
- `results/raw/m4-typed-decisions-coreml-perf.json`
- `results/raw/m4-typed-decisions-coreml-long.json`
- `results/raw/m4-typed-decisions-coreml-cpu-ne.json`
- `results/raw/m4-typed-decisions-mlx-perf.json`
- `results/raw/m4-typed-decisions-mlx-long.json`

Processed summary:

- `results/processed/m4-typed-decisions-421m-summary.json`