# Experiment Log

## 2026-09-23 — Baseline freeze and M4 upstream reproduction

### Environment

- Machine: Mac mini (Mac16,10)
- Chip: Apple M4, 10-core CPU / 10-core GPU / 16-core Neural Engine
- Unified memory: 24 GB
- macOS: 27.0 (26A428)
- Python: 3.12.14
- Core ML Tools: 9.0
- PyTorch: 2.7.0
- NumPy: 2.1.3
- MLX: 0.32.2
- laya-mlx: 0.2.0
- laya-coreml: 0.1.1
- Upstream source commit: `4619e0483f07adf39068532e85b42ec2347edb83`

The complete machine/software snapshot is stored in
`results/raw/environment-baseline.json`.

### Upstream test gate

Initial test run after installing research dependencies:

- 76 passed
- 6 failed because the optional demo dependency Pillow was absent.

After installing the upstream `demo` extra:

- **82 passed**
- 0 failed
- 3 Core ML / NumPy conversion warnings

The dependency-only failure is considered resolved.

### Published bundles

Pinned public bundles:

- ANE FP16: `aac6fef/laya-multilingual-coreml-ane@39d6a9b3d0f67f06da74fbade6121ea134cbdb21`
- ANE W8: `aac6fef/laya-multilingual-coreml-ane-w8@7503714810747a879b1e310074a9398bc573e739`
- Source: `convaiinnovations/laya-multilingual@052592a15d198d9ad47da779604259b10b47b7aa`

### NumPy M4 matmul warning

The published ANE runtime emits these warnings in the host FP32 action-head matmul:

- divide by zero encountered in matmul
- overflow encountered in matmul
- invalid value encountered in matmul

Diagnostics showed:

- pooled activations, action features, action input, weights, biases and matmul outputs were all finite;
- action input max absolute value: 242.625;
- first action-head weight max absolute value: 0.0739746;
- matmul result remained finite, approximately [-569.53, 1000.83];
- public predictions remained finite and passed the upstream finite-output checks;
- a standalone 32×32 float32 identity matmul reproduced the same three warnings on this M4 while producing an exactly correct identity matrix;
- a random float32 matmul remained finite and differed from a direct `einsum` reference by only about 3.8e-5.

This matches a known class of NumPy/Apple Silicon M4 false floating-point warnings. We therefore retain the upstream pinned NumPy 2.1.3 environment and do not alter the runtime for the benchmark. The warnings remain visible rather than being globally suppressed.

### Single-workload screening

One-question upstream short workload, 91 real tokens padded to L96, 10 warmup + 100 measured calls:

| Backend | P50 | P95 | Mean | Stable |
|---|---:|---:|---:|---|
| ANE FP16 | 6.580 ms | 7.349 ms | 6.681 ms | yes |
| ANE W8 | 4.596 ms | 6.032 ms | 4.830 ms | yes |

These screening results are not used as the primary performance conclusion.

### Balanced sustained runtime comparison

Method:

- all three models resident;
- compiled MLX FP16 baseline exactly follows the upstream energy-benchmark options:
  - batch size 1
  - `compile=True`
  - prompt caching enabled
  - pad-to-multiple 32
- 8 invoice-state variants;
- 32 warmup calls per backend;
- 20-second saturated blocks;
- 3 balanced cycles;
- order per cycle:
  `MLX → ANE FP16 → ANE W8 → ANE W8 → ANE FP16 → MLX`;
- 5 seconds idle between blocks;
- no power telemetry in this phase.

Results:

| Backend | Blocks | Active time | Decisions | P50 | P95 | Mean interval | Decisions/s | Unstable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| compiled MLX FP16 | 6 | 120.046 s | 8,126 | 14.563 ms | 16.723 ms | 14.773 ms | 67.69 | 0 |
| ANE FP16 | 6 | 120.024 s | 18,729 | 6.327 ms | 7.035 ms | 6.408 ms | 156.04 | 0 |
| ANE W8 K-means | 6 | 120.014 s | 26,102 | 4.512 ms | 5.267 ms | 4.598 ms | 217.49 | 0 |

Mean-interval speedup against compiled MLX on this M4:

- ANE FP16: **2.305×**
- ANE W8: **3.213×**

Raw result:
`results/raw/m4-sustained-runtime-comparison.json`.

### Fidelity gate

The two published ANE bundles were independently revalidated against the pinned
upstream FP32 golden fixture:

| Bundle | Argmax | Max calibrated probability drift | 100-call repeat stability | Gate |
|---|---:|---:|---|---|
| FP16 L96 | 59/59 | 0.00292485 | stable | PASS |
| W8 L96 | 59/59 | 0.0143929 | stable | PASS |

The four fixture questions outside the fixed L96 / K32 bundle capacity remain
outside this claim. This is conversion fidelity, not broad task accuracy.

Raw result:
`results/raw/m4-release-validation.json`.

### PSTR-only system energy run

A dedicated system-power run used the upstream PSTR-only methodology after the
runtime comparison. All three models stayed resident; loading and warmup were
excluded. The same 8-item short-decision workload was run in 3 balanced cycles,
with six 20-second active blocks per backend.

| Backend | Decisions | Mean interval | Mean system power | System J/decision | Gross energy improvement vs MLX |
|---|---:|---:|---:|---:|---:|
| compiled MLX FP16 | 10,186 | 11.782 ms | 36.176 W | 0.42625 J | 1× |
| ANE FP16 | 22,029 | 5.448 ms | 17.866 W | 0.09733 J | **4.380×** |
| ANE W8 K-means | 30,634 | 3.918 ms | 18.696 W | 0.07324 J | **5.820×** |

Adjacent-idle-subtracted energy improvements were 6.488× for FP16 ANE and
8.169× for W8 ANE. Gross system energy is retained as the primary published
metric because it depends on fewer subtraction assumptions.

The upstream `benchmarks.energy_summary` audit was rerun against the raw file
and passed all structural and integration checks:

- 3 complete balanced cycles;
- 1,101 PSTR samples;
- maximum observed system power 48.327 W;
- maximum sample gap 0.515 s;
- all system-power samples positive, finite and below the 500 W sanity ceiling;
- active and adjacent-idle energy integrals recomputed consistently;
- all active blocks retained stable rounded decisions.

Complete-cycle bootstrap 95% ranges:

- W8 gross system-energy improvement: 5.674–6.010×;
- FP16 gross system-energy improvement: 4.319–4.478×.

Raw files:

- `results/raw/m4-pstr-energy.json`
- `results/raw/m4-pstr-energy-audit.json`

### Result privacy sanitation

Before repository review, local absolute home-directory paths and the local host
name were removed from publishable result metadata. Timing samples, model hashes,
revisions, outputs, fidelity metrics and all measured values were left unchanged.

Benchmark scripts now emit project-relative paths by default, and the environment
snapshot intentionally records only the executable's project-relative path plus
non-identifying OS/hardware fields.

### Interpretation status

Verified:

1. The published L96 ANE bundles run correctly on the M4 Mac mini.
2. On this machine and workload, both ANE paths substantially outperform the
   compiled MLX FP16 baseline.
3. W8 is consistently faster than FP16 across all balanced cycles, not only in
   the initial screening run.
4. Both ANE bundles pass the upstream fidelity gate.
5. PSTR-only system-power measurement shows materially lower gross system energy
   per decision for both ANE paths than for compiled MLX on this workload.
6. The saved energy run passes the upstream structural, telemetry and
   re-integration audit.

Not yet verified:

1. Runtime hardware-trace evidence that every heavy operation actually executed
   on ANE on this specific machine.
2. Whether the unusually large W8-vs-FP16 advantage is caused primarily by
   memory bandwidth, ANE generation differences, Core ML scheduling, or another
   factor.
3. Ordinary Core ML CPU/GPU baseline behavior under the same workload.
4. 421M Typed Decisions ANE feasibility.

## 2026-09-23 — Phase 2: Typed Decisions 421M runtime baseline

### Pinned artifacts

- Core ML bundle: `aac6fef/laya-typed-decisions-coreml`
- Core ML Hub revision:
  `28d24fa8d67a3264556b23391ec6c3fd98573056`
- Source checkpoint: `convaiinnovations/laya-typed-decisions`
- Source revision:
  `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`
- Core ML package: B1, enumerated L16–L1024, K32, FP16 SDPA
- Published package SHA-256:
  `517a8071290a29c2f1e19b38356fdc5c59dfdc801711a92606de6bba67596c85`

### Independent M4 conversion-fidelity validation

The pinned Hub bundle was tested against the upstream frozen FP32 reference on
the M4, not merely trusted from its bundled release report.

- selected-answer agreement: **63/63**
- maximum calibrated probability drift: **0.0027266348**
- maximum action-probability drift: **0**
- repeat stability: **100/100 identical rounded public results**
- repeat phase elapsed: 239.250 s
- gate: **PASS**

The upstream temperature-safety logic emits a warning for the `choice:11+`
temperature bucket and clamps it into the accepted range. Confidence involving
that bucket is therefore not treated as broadly calibrated.

Primary raw file:
`results/raw/m4-typed-decisions-coreml-validation.json`.

### Primary short runtime comparison

Boundary: complete synchronous `predict`; load/warmup excluded. Ten warmup
calls, then 100 measured calls per workload.

| Questions | Core ML CPU+GPU P50 / P95 | MLX FP16 P50 / P95 | P50 relation |
|---:|---:|---:|---:|
| 1 | **33.715 / 35.948 ms** | 36.055 / 38.129 ms | Core ML 1.069× faster |
| 3 | 102.174 / 106.290 ms | **84.492 / 87.856 ms** | MLX 1.209× faster |
| 10 | 350.114 / 369.038 ms | **242.303 / 249.021 ms** | MLX 1.445× faster |

The multi-question rows are shipped-API comparisons rather than equal tensor
batching. The ordinary Core ML path executes questions sequentially; MLX uses
batch size 16.

Primary raw files:

- `results/raw/m4-typed-decisions-coreml-perf.json`
- `results/raw/m4-typed-decisions-mlx-perf.json`

Earlier screening/probe runs are retained as raw exploratory data rather
than deleted:

- `results/raw/m4-typed-decisions-coreml-short.json`
- `results/raw/m4-typed-decisions-mlx-short.json`
- `results/raw/m4-typed-decisions-coreml-plan.json` (single-sample compute-plan probe)

### Full-length L1024 single question

50 measured calls after 10 warmups:

- Core ML CPU+GPU: **304.921 ms P50**, 311.638 ms P95
- MLX FP16: **312.202 ms P50**, 319.886 ms P95

The two routes are near parity for this workload in this desktop run.

### Startup observations

Primary short runs:

- Core ML load: 19.981 s
- MLX load: 1.145 s
- first Core ML short prediction: 3329.190 ms
- first MLX short prediction: 120.327 ms

These are observed cache-state values, not controlled cold-boot results.

### Ordinary CPU+NE control

To test whether compute-unit selection alone could unlock the Neural Engine,
the same ordinary SDPA package was run with `cpu_ne`:

- 1-question P50: **1204.469 ms**
- P95: 1265.859 ms
- roughly 35.7× slower than CPU+GPU P50

Anticipated compute plan:

- preferred CPU operations: 1,643
- preferred Neural Engine operations: **0**
- ANE-supported operations: 1,228

Therefore ANE support in the operator set is not equivalent to ANE placement.
The ordinary 421M export requires a graph rewrite to become a meaningful ANE
candidate.

### Phase 2 status

**PASS.**

The 421M CPU+GPU and MLX runtime baseline is frozen. Phase 3 proceeds to the
unified decision-quality benchmark; 421M ANE engineering remains gated behind
that quality evaluation and a dedicated structural feasibility review.

Processed summary:
`results/processed/m4-typed-decisions-421m-summary.json`.

Human-readable report:
`results/reports/M4-Typed-Decisions-421M-Baseline-v0.1.md`.



## 2026-09-23 — Phase 3A: public typed-decisions quality baseline

The public `LocalLLaMA/typed-decisions` test split was pinned at
`c76749ec58bd8c3d2ea706b31c333a9059c38f90` and evaluated with Laya Typed
Decisions 421M through the MLX FP16 public API.

All 400 cases / 2,000 decisions completed with 100% coverage.

Primary metrics:

- accuracy: **0.7660**
- soft accuracy: **0.470636**
- KL from gold: **0.117043**
- total variation: **0.174059**
- Brier vs soft gold: **0.061473**
- ECE (15 bins): **0.213283**
- score MAE: **0.242418**
- within one score level: **0.995**

The result reproduces the published Laya specialist benchmark row to rounding
precision, providing an external sanity check on the local scorer.

End-to-end case latency on the M4:

- P50: 513.672 ms
- P95: 2838.582 ms
- P99: 5337.657 ms
- mean: 830.019 ms
- total measured run: 415.962 s

The benchmark uses one public `predict` call per case with all five questions
present. The checkpoint consumed 582,370 input tokens and generated zero output
tokens.

Important interpretation boundary: Laya Typed Decisions 421M is treated as a
specialist for this benchmark task family. Jev 1.13.0 is evaluated as a
zero-shot generalist. Their scores may be reported side by side only with this
training-regime distinction made explicit.

Raw:
`results/raw/m4-typed-decisions-quality-mlx.json`

Processed:
`results/processed/m4-typed-decisions-quality-mlx-summary.json`

Report:
`results/reports/M4-Typed-Decisions-Quality-Laya-v0.1.md`


## 2026-09-23 — Phase 3C: published ANE × typed-decisions capacity audit

The published `aac6fef/laya-multilingual-coreml-ane-w8` bundle was audited
against the same pinned public Typed Decisions test split before attempting any
quality scoring.

Bundle facts:

- source: `convaiinnovations/laya-multilingual`
- source revision: `052592a15d198d9ad47da779604259b10b47b7aa`
- shape: B1 / L96 / K32
- precision: FP16 graph with selected convolution weights compressed to W8

The audit uses the bundle's own tokenizer, RL config and prompt construction,
but deliberately does not load the Core ML model.

Result:

- supported at L96: **0 / 2,000 decisions**
- capacity coverage: **0%**
- minimum prompt length: 127 tokens
- median prompt length: 323 tokens
- P95: 450 tokens
- P99: 575 tokens
- maximum: 631 tokens
- options: 2–5, so K32 is not limiting

Every workflow and every question type is fully over capacity.

Hypothetical fixed-length coverage for the same unmodified prompts:

- L128: 3 / 2,000 (0.15%)
- L160: 110 / 2,000 (5.50%)
- L192: 472 / 2,000 (23.60%)
- L256: 622 / 2,000 (31.10%)
- L384: 1,597 / 2,000 (79.85%)
- L512: 1,961 / 2,000 (98.05%)
- L640: 2,000 / 2,000 (100%)

No ANE quality score is produced. Truncating state, instructions or criteria
would change the benchmark, so over-capacity inputs are recorded as unsupported
rather than counted as wrong.

This is not evidence that the published ANE artifact is defective; it is an
input-shape incompatibility between an L96 short-decision export and this
longer-context quality benchmark.

Raw:
`results/raw/m4-laya-ane-w8-typed-decisions-capacity.json`

Processed:
`results/processed/m4-laya-ane-w8-typed-decisions-capacity-summary.json`

Report:
`results/reports/M4-Laya-ANE-W8-Typed-Decisions-Capacity-v0.1.md`



## 2026-09-23 — Phase 3D: 421M Core ML vs MLX full-quality parity

The full 400-case / 2,000-decision public Typed Decisions test split was run
through the ordinary 421M Core ML CPU+GPU export and compared decision by
decision with the Phase 3A MLX FP16 run.

Parity:

- decisions compared: **2,000**
- selected-answer mismatches: **0**
- mismatch cases: **0**
- max probability absolute delta: 0.0030
- max Score-value delta: 0.0039
- max Noul delta: 0.0049
- max confidence delta: 0.0049
- max action-probability delta: 0

Aggregate quality:

- accuracy: 0.766000 on both backends
- soft-accuracy delta (Core ML − MLX): +0.00000485
- KL delta: +0.00000272
- total-variation delta: +0.00000277
- Brier delta: −0.00000022
- ECE delta: −0.00001153
- Score MAE delta: −0.00002704
- within-one-level delta: 0

This establishes full-task quality parity for the same 421M checkpoint. The
small numeric deltas do not change any selected decision.

End-to-end five-question case latency:

- Core ML CPU+GPU P50: 887.877 ms
- MLX FP16 P50: 513.672 ms
- Core ML / MLX P50: 1.728×
- Core ML mean: 1938.453 ms
- MLX mean: 830.019 ms
- Core ML / MLX mean: 2.335×
- Core ML load: 18.945 s
- MLX load: 1.152 s

These first-pass case latencies include shape-specialization effects after model
load. The warmed Phase 2 microbenchmark remains the correct source for
steady-state short-input latency.

Raw Core ML:
`results/raw/m4-typed-decisions-quality-coreml.json`

Comparison:
`results/processed/m4-typed-decisions-quality-coreml-vs-mlx.json`

Report:
`results/reports/M4-Typed-Decisions-421M-CoreML-vs-MLX-Quality-Parity-v0.1.md`



## 2026-09-23 — Phase 3B status: Jev runner ready, credential gate confirmed

The Jev HTTP adapter and full typed-decisions runner are implemented. Current
official TypeSafe API documentation requires Bearer authentication for the API,
and a direct unauthenticated `GET /v1/models` from the benchmark host returned
HTTP 403 with an authentication error.

No TypeSafe API key is exposed to the current benchmark execution environment,
so a local Jev rerun has not been fabricated from cached or third-party results.

An external reference has instead been pinned separately:

- source: public `LocalLLaMA/typed-decisions` dataset card
- measurement date reported by source: 2026-09-18
- model requested: `jev-latest`
- concrete model reported by response: `jev-1.13.0`
- mode: general / zero-shot
- cases / decisions: 400 / 2,000
- errors: 0
- accuracy: 0.727
- soft accuracy: 0.580
- KL: 1.442
- TV: 0.251
- Brier: 0.148
- ECE: 0.144
- Score MAE: 0.391
- within one level: 0.952
- P50: 710 ms/case

These values remain labelled **external**, not locally measured.

The local Laya Typed Decisions 421M checkpoint is a specialist fine-tuned on
the benchmark's 1,200-case train split / 6,000 decisions. Jev is reported as a
zero-shot generalist, so the two rows must not be turned into an overall model
ranking.

Reference provenance:
`references/JEV_TYPED_DECISIONS.md`

Phase 3 interim report:
`results/reports/Phase3-Jev-Laya-ANE-Interim-v0.1.md`



## 2026-09-23 — Jev credential plumbing hardened

The benchmark host was checked for existing TypeSafe/Jev credentials without
reading secret values.

Checked sources:

- current AgentDock process environment
- launchd environment
- macOS generic and internet-password Keychain metadata
- common user secret files and their variable names
- Codex / Hermes environment variable names

No existing TypeSafe/Jev/SystemOne credential was found.

The Jev adapter now resolves credentials in this order:

1. `TYPESAFE_API_KEY` environment variable;
2. macOS Keychain service `typesafe-systemone`, current macOS account by default.

Only the credential-source label is written to benchmark metadata; the key is
never serialized.

A secure one-time helper was added:

`scripts/configure_typesafe_keychain.sh`

It uses the macOS `security` CLI with interactive password prompting
(`-w` as the final option), so the API key is not placed in shell history or
the command-line argument list.

After the Keychain item is created, the existing Phase 3B runner can execute
without further code changes.



## 2026-09-23/24 — Phase 3B complete: local Jev 1.13.0 replay

The TypeSafe credential was stored in macOS Keychain and the local Jev adapter
was hardened for the benchmark host:

- Keychain account resolution uses the real process UID rather than
  `getpass.getuser()`, because AgentDock's child environment reported
  `getpass=root` while the host UID belongs to `zhongshengyuan`.
- API requests retry bounded transient failures (SSL/URL/timeouts and HTTP
  408/429/5xx) with exponential backoff.
- the secret value is never serialized; only the non-secret credential-source
  label is saved.

Model discovery returned `jev-latest` and `jev-preview`. The benchmark
therefore requests `jev-latest`; every completed response in the full run
reported concrete model `jev-1.13.0`.

### Full local Jev run

Public Typed Decisions test split:

- 400 / 400 cases
- 2,000 / 2,000 decisions
- zero API errors
- accuracy: **0.7370**
- soft accuracy: 0.53836
- KL from gold: 1.50336
- total variation: 0.25002
- Brier vs soft gold: 0.14774
- hard-label ECE (15 bins): 0.04218
- Score MAE: 0.38757
- within one score level: 0.95125
- end-to-end P50: 960.09 ms/case
- P95: 1833.32 ms/case
- total elapsed: 534.43 s
- API usage: 378,236 input tokens / 54,064 output tokens

### Public Sep 18 comparison

The public Jev benchmark measurement commit and the locally pinned dataset
revision contain byte-identical test parquet data:

SHA-256:
`4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`

Therefore dataset drift is not the reason the public accuracy (0.727) differs
from the local rerun (0.737).

### Repeatability probe

The first 100 cases were immediately requested again.

Compared over 500 decisions:

- exact answer objects: 77 / 500
- selected-label flips: **9 / 500 (1.8%)**
- maximum probability delta: 0.15
- maximum confidence delta: 0.14
- flip correctness transitions:
  - 4 wrong → right
  - 3 right → wrong
  - 2 wrong → different wrong

Aggregate accuracy on those same 100 cases changed only 0.632 → 0.634.

This establishes observable live-endpoint nondeterminism. It can plausibly
contribute to historical/local metric differences; unversioned serving-stack
changes cannot be ruled out.

### Phase 3 close

Phase 3 is complete. Final report:

`results/reports/Phase3-Jev-Laya-ANE-Final-v1.0.md`

Next gate:

**Phase 4A — 421M long-context ANE feasibility**, staged at L192 → L384 → L512
before any L640 full-coverage attempt.



## 2026-09-24 — Phase 4A: Typed Decisions 421M ANE L192

Phase 4A began with the pinned Laya Typed Decisions 421M checkpoint
(`f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`).

Architecture comparison showed the 421M checkpoint is substantially heavier in
the transformer body than the published 322M multilingual ANE checkpoint:

- hidden size: 1024 vs 768
- encoder layers: 28 vs 22
- attention heads: 16 vs 12
- FFN intermediate: 2624 vs 1152
- non-embedding parameters: ~369.7M vs ~125.3M

The upstream ANE research implementation was first reviewed. Importantly, the
upstream 322M research tree already contains successful L192 and L1024 fixed-body
experiments with all attributed operations preferred on ANE, so long-context
ANE feasibility was not treated as an unexplored principle.

### Single-layer L192 preflight

421M representative layer:

- preferred ANE operations: 368
- preferred CPU/GPU operations: 0
- P50: 2.372 ms
- PyTorch layout max error: 2.67e-5
- Core ML max abs error: 0.0710
- Core ML RMSE: 0.00302

The numerical error is no worse than the upstream 322M research layer
(max abs 0.1496, RMSE 0.00392).

### Full L192 body

- fixed shape: B1 / L192 / K32
- package size: 741,741,391 bytes (~707 MiB)
- conversion: 155.35 s
- first load + AOT compile: 158.41 s
- preferred ANE operations: **10,594**
- preferred CPU/GPU operations: **0**
- attributed estimated cost on ANE: ~100%
- body P50: **32.14 ms**
- body P95: 47.74 ms

The original upstream research probe re-loads the compiled model to obtain an
MLComputePlan, which triggers another expensive AOT path for this large graph.
This was observed directly and should be avoided when placement evidence is not
needed.

### L192 golden fidelity

A local validation path was added that reuses the upstream FP32 golden but does
not recompute the compute plan.

- reference cases evaluated: 15 / 16
- questions: 60
- argmax: **60 / 60**
- max calibrated probability error: **0.00640**
- max action probability error: **0**
- repeats: **100 / 100 identical**
- end-to-end short1 P50: **50.05 ms**
- gate: **PASS**

The single skipped reference case is L1024.

The checkpoint has extremely saturated FP32 golden action logits (up to about
±5,000). The host action path emitted numerical matmul warnings and raw action
logit drift reached 64.1 in one case, but action probabilities remained exactly
aligned with the golden on all evaluated questions. This is tracked as a
host-path numerical-stability observation rather than an ANE fidelity failure.

### Capacity and decision

Unmodified public Typed Decisions prompts fitting L192:

- 472 / 2,000 decisions
- 23.6% coverage

The L192 gate passes structural conversion, ANE placement, golden fidelity and
repeatability.

Proceed to L384. The L192 short1 latency is not compared directly with the MLX
short-input result because the fixed ANE graph always computes all 192 tokens.

Processed summary:
`results/processed/phase4a-typed421-l192-summary.json`

Report:
`results/reports/Phase4A-Typed421-L192-v0.1.md`## 2026-09-24 — Phase 4 frozen: 421M long-context ANE engineering

Phase 4 is complete and frozen. The project extended the upstream ANE research path to the 421M Typed Decisions checkpoint and validated fixed full-body L192, L384, L512 and L640 artifacts.

Key conclusions:

- all tested full-body shapes converted successfully;
- the Core ML anticipated execution plan preferred Neural Engine for all 10,594 attributed nonconstant operations at every tested shape;
- 60/60 naturally covered golden questions agreed at every validation shape;
- max calibrated probability error was 0.0064013 and action probability error was zero;
- 100-call rounded-output repeat stability passed;
- the 421M tokenizer gives L512 capacity of 1,966/2,000 decisions (98.3%) and full coverage by L608;
- L512 ANE vs matched-subset MLX selected agreement was 99.8% (4/1,966 boundary flips);
- balanced representative PSTR measurement showed 2.074x gross system-energy-per-decision improvement for L512 ANE vs MLX, with complete-cycle bootstrap range 1.798x–2.334x;
- L640 reached 2,000/2,000 coverage but its median single-decision latency lost to MLX;
- a static short-MLX / medium-L512-ANE / long-MLX router preserved 1,996/2,000 selected decisions;
- runtime-state sensitivity remains observed for the same L512 package, while thermal throttling is not proven.

Product decision:

Stop expanding fixed shapes for their own sake. Proceed to Phase 5 Local System One MVP with MLX fallback, L512 ANE acceleration, routing, and ANE health gating.

Canonical report:
results/reports/Phase4-421M-ANE-Engineering-Final-v1.0.md

## 2026-09-24 — Phase 5 started: Local System One MVP

Product code now exists in local_system_one/ with:

- normalized Choice / Score / Noul schemas;
- MLX and L512 ANE runtime adapters;
- configurable token-length routing;
- ANE startup/runtime health gate;
- transparent MLX fallback;
- privacy-safe in-memory metrics;
- loopback-first standard-library HTTP service and CLI.

Validation:

- unit suite: 12/12 pass;
- MLX-only real HTTP smoke passed on the 421M checkpoint;
- a 93-token request routed short_input -> MLX and returned a valid Choice response;
- real L512 service startup completed, but the startup probe observed 166.5 ms P50 against the initial 125 ms health envelope;
- ANE was therefore marked degraded;
- a subsequent 444-token request transparently routed ane_unhealthy -> MLX and completed successfully;
- no raw request payload is stored by the service metrics path.

This confirms that the Phase 4 runtime-state sensitivity is now handled as a product health/fallback concern instead of being ignored.
