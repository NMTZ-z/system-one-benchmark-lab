# Jev 1.13.0 × Typed Decisions — Local Independent Rerun v0.1

Run window: 2026-09-23/24 (+08:00)

## Scope

This is an independent replay of the public
`LocalLLaMA/typed-decisions` test split through the live TypeSafe API.

- request model: `jev-latest`
- concrete model reported by every completed response: **`jev-1.13.0`**
- benchmark revision:
  `c76749ec58bd8c3d2ea706b31c333a9059c38f90`
- test parquet SHA-256:
  `4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`
- cases: 400
- decisions: 2,000
- mode: general / zero-shot
- errors: **0**
- credentials: macOS Keychain; the secret itself is never serialized

The Jev row is directly comparable to the public Jev benchmark as a rerun of the
same API shape and the same test data. It is **not** directly comparable as a
training-regime ranking against the Laya Typed Decisions specialist.

## Local result

| Metric | Local Jev 1.13.0 |
|---|---:|
| Coverage | **100%** |
| Accuracy | **0.7370** |
| Soft accuracy | 0.53836 |
| KL from gold | 1.50336 |
| Total variation | 0.25002 |
| Brier vs soft gold | 0.14774 |
| ECE, 15-bin hard-label | 0.04218 |
| Mean top probability | 0.75587 |
| Score MAE | 0.38757 |
| Within 1 score level | 0.95125 |

The run used the same local scoring implementation used for the Laya runs.

## By workflow

| Workflow | Accuracy | Soft acc | KL | Brier | ECE | Score MAE |
|---|---:|---:|---:|---:|---:|---:|
| agent_trace_observability | 0.632 | 0.4540 | 1.4089 | 0.2097 | 0.1120 | 0.4962 |
| customer_service | **0.790** | 0.5926 | 1.7140 | 0.1118 | **0.0375** | **0.2190** |
| invoice_processing | 0.780 | **0.6084** | **0.5674** | 0.1197 | 0.0878 | 0.3363 |
| security_incidents | 0.746 | 0.4986 | 2.3231 | 0.1498 | 0.0745 | 0.4988 |

The aggregate score hides a large workflow spread. Agent-trace observability is
materially harder for this run than customer service or invoice processing.

## By decision type

| Type | n | Accuracy | Soft acc | KL | Brier | ECE |
|---|---:|---:|---:|---:|---:|---:|
| Choice | 600 | 0.7283 | 0.5146 | 1.3969 | 0.1247 | 0.0486 |
| Noul | 600 | **0.7933** | **0.6339** | **0.0944** | **0.0704** | 0.0810 |
| Score | 800 | 0.7013 | 0.4846 | 2.6400 | 0.2230 | 0.0985 |

Score-only metrics:

- Score MAE: 0.38757
- within one level: 0.95125

The Score primitive is the weakest distributional slice in this run: it has
the highest KL and Brier and the lowest accuracy among the three primitive
families.

## End-to-end API latency

Each benchmark case is one HTTP request containing five questions.

| Metric | Local client → TypeSafe API |
|---|---:|
| Mean / case | 1181.6 ms |
| P50 / case | **960.1 ms** |
| P95 / case | 1833.3 ms |
| P99 / case | 6749.9 ms |
| Min / max | 776.3 / 9427.8 ms |
| Total run | 534.4 s |

Usage reported by the API:

- input tokens: 378,236
- output tokens: 54,064

These are hosted end-to-end numbers from this client's network path. They are
not a hardware benchmark against local MLX/Core ML.

## Comparison with the public 2026-09-18 Jev measurement

The public dataset card reports an earlier full run through `jev-latest`, also
reporting concrete model `jev-1.13.0`.

| Metric | Public Sep 18 | Local rerun | Local − public |
|---|---:|---:|---:|
| Accuracy | 0.727 | **0.737** | +0.010 |
| Soft accuracy | **0.580** | 0.538 | −0.042 |
| KL | **1.442** | 1.503 | +0.061 |
| TV | 0.251 | **0.250** | −0.001 |
| Brier | 0.148 | **0.1477** | −0.0003 |
| ECE | 0.144 | **0.0422** | −0.1018 |
| Score MAE | 0.391 | **0.3876** | −0.0034 |
| Within 1 level | 0.952 | 0.9513 | −0.0008 |
| P50 / case | **710 ms** | 960 ms | +250 ms |

The public and local runs used byte-identical test parquet data. The parquet
SHA-256 at the public Jev measurement commit and at the locally pinned revision
is identical, so dataset drift is ruled out as the explanation.

The two measurements should still not be treated as bit-identical repetitions.
The live endpoint shows observable nondeterminism.

## Repeatability check

The first 100 cases were requested a second time immediately after the full
run.

- common cases: 100
- decisions compared: 500
- exact answer objects: 77 / 500
- selected-label flips: **9 / 500 = 1.8%**
- maximum probability delta: 0.15
- maximum confidence delta: 0.14

Among the 9 label flips:

- 4 changed wrong → right
- 3 changed right → wrong
- 2 changed wrong → a different wrong answer

The first-100 aggregate accuracy moved only from 0.632 to 0.634 despite the
9 decision flips.

This demonstrates that the hosted output is not bitwise deterministic under the
observed conditions. It makes it unsafe to interpret differences such as
0.727 vs 0.737 as immutable properties of a fixed binary.

Observed nondeterminism can plausibly contribute to the public/local metric
difference. Serving-stack behavior can also change without a visible concrete
model-label change. This experiment does not distinguish those two mechanisms.

## ECE note

The local ECE is a 15-bin top-probability vs hard-label correctness metric. The
same implementation reproduces the published Laya ECE on the local Laya run.

The public Jev ECE (0.144) does not reproduce in the current API run:

- current hard-label ECE: 0.0422
- using Jev's explicit confidence field where present: about 0.0825

The public Jev ECE therefore remains an external historical measurement. The
difference is recorded rather than "corrected" to force agreement.

## Interpretation

This rerun establishes that Jev 1.13.0 remains a strong zero-shot general
System One endpoint on this benchmark, with complete schema coverage and no API
errors in the 400-case run.

It also establishes that the live endpoint has non-zero repeat variance. Any
production policy that gates behavior on narrow probability thresholds should
therefore validate repeatability and calibration on the deployment workload,
not only read a single benchmark row.

## Files

Full raw run:

- `results/raw/typed-decisions-quality-jev-1.13.0.json`

100-case repeat:

- `results/raw/typed-decisions-jev-repeat100.json`

Initial smoke:

- `results/raw/typed-decisions-jev-smoke.json`

Processed summary:

- `results/processed/typed-decisions-jev-1.13.0-local-summary.json`

Repeatability comparison:

- `results/processed/typed-decisions-jev-repeatability.json`

Repeat comparator:

- `benchmarks/quality/compare_repeats.py`