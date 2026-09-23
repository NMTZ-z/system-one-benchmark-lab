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
