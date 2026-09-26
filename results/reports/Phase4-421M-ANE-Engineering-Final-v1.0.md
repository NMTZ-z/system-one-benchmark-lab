# Phase 4 Final — 421M Typed Decisions on Apple Neural Engine

Date: 2026-09-24

## Purpose

Phase 4 asked whether the open 421M Laya Typed Decisions checkpoint could move from MLX / ordinary Core ML onto Apple Neural Engine at useful context lengths without losing practical decision quality or efficiency.

Answer: **yes**, with one important qualification. The largest fixed ANE shape is not the best default runtime.

Phase 4 is now frozen. Future work moves from conversion research to a usable Local System One service.

## Contribution boundary

### Upstream work

These are upstream contributions and are not claimed as original work here:

- Laya model family and the 421M Typed Decisions checkpoint;
- the 421M weights;
- the original public 322M multilingual ANE work;
- the underlying ANE graph-rewrite approach and research runtime;
- the public Typed Decisions dataset.

### Work completed in this project

This project extends that foundation by:

1. adapting the ANE research graph to the 421M Typed Decisions checkpoint;
2. validating full 28-layer fixed-shape bodies at L192, L384, L512 and L640;
3. measuring anticipated Core ML device placement for every shape;
4. validating conversion fidelity and repeated-output stability;
5. evaluating the fixed-shape models on the real 2,000-decision test set;
6. measuring matched MLX vs ANE latency;
7. measuring balanced PSTR-only system energy on a representative real-workload sample;
8. testing full-coverage L640 and practical MLX + L512 ANE routing;
9. identifying runtime-state sensitivity as the remaining production issue.

The original contribution is an **engineering extension and runtime architecture**, not a newly trained 421M model.

## Fixed-shape feasibility

| Shape | Package | Conversion | Load / AOT compile | Preferred ANE ops | Validation |
|---|---:|---:|---:|---:|---:|
| L192 | 707.4 MiB | 155.3 s | 158.4 s | 10,594 / 10,594 | PASS |
| L384 | 707.4 MiB | 144.6 s | 188.7 s | 10,594 / 10,594 | PASS |
| L512 | 707.5 MiB | 181.0 s | 199.9 s | 10,594 / 10,594 | PASS |
| L640 | 707.5 MiB | 143.4 s | 171.5 s | 10,594 / 10,594 | PASS |

Preferred ANE ops comes from the Core ML anticipated execution plan. It is not a hardware execution trace.

For every tested shape:

- 60 / 60 naturally covered validation questions preserved selected answers;
- maximum probability error was 0.0064013;
- action probability error was 0;
- 100 repeated calls produced identical rounded results.

## Capacity with the 421M tokenizer

The earlier 322M multilingual capacity curve must not be reused because its tokenizer/config differs.

| Fixed length | Supported decisions | Coverage |
|---|---:|---:|
| L96 | 0 / 2,000 | 0.0% |
| L128 | 17 | 0.85% |
| L160 | 127 | 6.35% |
| L192 | 499 | 24.95% |
| L256 | 647 | 32.35% |
| L384 | 1,814 | 90.70% |
| L512 | **1,966** | **98.30%** |
| L576 | 1,995 | 99.75% |
| L608 | **2,000** | **100%** |
| L640 | **2,000** | **100%** |

L512 is therefore the useful engineering point: near-full coverage without always paying for the largest graph.

## L512 quality

L512 naturally executes 1,966 / 2,000 decisions, with 34 over-capacity and zero runtime errors.

| Metric | L512 ANE | Same-subset MLX |
|---|---:|---:|
| Accuracy | 0.76501 | 0.76399 |
| Soft accuracy | 0.47090 | 0.47089 |
| KL | 0.11690 | 0.11692 |
| Brier | 0.06143 | 0.06144 |
| ECE15 | 0.21226 | 0.21124 |
| Score MAE | 0.24363 | 0.24368 |
| Within 1 | 0.99491 | 0.99491 |

Parity:

- decisions compared: 1,966;
- selected-answer mismatches: **4**;
- agreement: **99.80%**;
- max probability delta: 0.0051;
- max score delta: 0.0126;
- max Noul delta: 0.0037;
- action probability delta: 0.

All four selected-answer changes occur on near-tied top probabilities, consistent with small numerical perturbations crossing an argmax boundary.

## Matched single-decision latency

| Backend | Mean | P50 | P95 |
|---|---:|---:|---:|
| L512 ANE | 83.97 ms | **78.35 ms** | 126.77 ms |
| MLX FP16, batch 1 | 130.52 ms | 97.31 ms | 339.17 ms |

- P50 speedup: about 1.24×
- mean speedup: about 1.55×

The benefit is workload-dependent. Very short inputs can favor MLX because a fixed L512 graph still pays the full shape cost.

## Representative real-workload energy

A deterministic 128-decision sample was selected across the token-length distribution of the 1,966 L512-supported decisions.

Token length: min 124, P25 190, median 305.5, P75 351.25, P95 410.2, max 510.

Measurement:

- both models resident;
- MLX batch size 1;
- 3 balanced cycles;
- MLX → ANE → ANE → MLX per cycle;
- six 20-second active blocks per backend;
- PSTR-only SMC system-power sampler;
- loading and warmup excluded.

| Backend | Mean interval | Mean system power | Gross J / decision |
|---|---:|---:|---:|
| MLX | 102.69 ms | 41.76 W | 4.288 J |
| L512 ANE | 88.97 ms | 23.24 W | **2.068 J** |

ANE vs MLX:

- speed: **1.154×**;
- average system-power reduction factor: **1.797×**;
- gross system-energy improvement: **2.074×**;
- adjacent-idle-subtracted energy improvement: 5.429×.

Complete-cycle bootstrap 95% range for gross energy improvement: **1.798×–2.334×**.

This is an SMC PSTR system estimate, not a calibrated external wall-power meter.

## Shape mismatch matters

A short-workload control intentionally ran the fixed L512 graph on much shorter inputs. MLX was substantially faster and L512 ANE was slightly worse in gross energy per decision.

Core product conclusion:

> A large fixed ANE graph is not automatically the best backend for every input.

The useful architecture is routing, not ANE everywhere.

## L640 full coverage

L640 proves full-coverage feasibility:

- 2,000 / 2,000 decisions;
- zero over-capacity;
- zero runtime errors;
- accuracy 0.767;
- MLX reference accuracy 0.766;
- 4 / 2,000 selected-answer mismatches;
- max probability delta 0.0051.

But median single-decision latency is:

| Backend | P50 |
|---|---:|
| MLX FP16 | **98.17 ms** |
| L640 ANE | 172.14 ms |

L640 therefore proves feasibility but does not justify using the largest fixed shape by default. The capacity audit also shows L608 already covers all current 2,000 decisions.

## Hybrid runtime experiment

Tested static policy:

- tokens below 192 → MLX;
- 192 through 512 → L512 ANE;
- above 512 → MLX.

Routes:

- MLX short: 497;
- L512 ANE: 1,469;
- MLX long: 34.

Coverage is 2,000 / 2,000. Against frozen MLX, selected agreement is **1,996 / 2,000 = 99.8%**.

The 192-token threshold is an experimental baseline, not an optimized production threshold.

## Remaining production issue: runtime-state sensitivity

The same L512 package showed materially different valid latency modes:

- validation short1 P50: about 75.7 ms;
- full-subset P50: about 78.4 ms;
- balanced energy blocks: roughly 88–95 ms;
- hybrid-router ANE branch: about 139.9 ms.

macOS reported no thermal/performance warning during these observations.

Therefore runtime-state sensitivity is observed, thermal throttling is not proven, and production code must health-gate ANE instead of assuming fixed latency.

## Phase gate

| Gate | Result |
|---|---|
| 421M long-context structural feasibility | **PASS** |
| L512 quality | **PASS** |
| L512 representative energy | **PASS** |
| L640 full-coverage quality | **PASS** |
| Static hybrid-router quality | **PASS** |
| Production readiness | **CONDITIONAL** |

The condition is runtime health management and integration, not further model conversion.

## Decision

Phase 4 is frozen.

Do not spend the next cycle building larger fixed shapes or synthetic benchmarks merely to accumulate measurements.

Proceed to **Phase 5 — Local System One MVP**.

Product hypothesis:

> A local decision service using MLX for short/fallback traffic and L512 ANE for suitable workloads can provide a low-cost, low-energy System One layer for personal agents while preserving the 421M specialist's practical decision quality.

That hypothesis must now be tested in real agent workflows.