# M4 Laya ANE Baseline v0.1

Date: 2026-09-23

## Executive summary

The upstream Laya ANE implementation was reproduced successfully on a base
Apple M4 Mac mini with 24 GB unified memory.

Under a balanced sustained short-decision workload, the published FP16 ANE
bundle is **2.305× faster** than compiled MLX FP16 by mean interval per decision,
while the published W8 K-means ANE bundle is **3.213× faster**.

Both ANE bundles independently pass the upstream fixed-capacity conversion
fidelity gate.

## Reproducibility anchor

- laya-coreml commit:
  `4619e0483f07adf39068532e85b42ec2347edb83`
- source checkpoint:
  `convaiinnovations/laya-multilingual@052592a15d198d9ad47da779604259b10b47b7aa`
- ANE FP16 bundle:
  `aac6fef/laya-multilingual-coreml-ane@39d6a9b3d0f67f06da74fbade6121ea134cbdb21`
- ANE W8 bundle:
  `aac6fef/laya-multilingual-coreml-ane-w8@7503714810747a879b1e310074a9398bc573e739`

## Machine

- Mac mini
- Apple M4
- 24 GB unified memory
- macOS 27.0
- Python 3.12.14
- coremltools 9.0
- MLX 0.32.2
- laya-mlx 0.2.0
- NumPy 2.1.3

Apple lists the base M4 Mac mini as a 10-core GPU system with a 16-core Neural
Engine and 120 GB/s memory bandwidth. The upstream published comparison used an
M3 Max with a 40-core GPU and 400 GB/s memory bandwidth, so cross-machine
differences must not be interpreted as a clean chip-generation A/B test.

## Sustained short-decision result

All models were resident. Loading and warmup were excluded. The workload used
the same eight short invoice-state variants as the upstream final energy test.
Each backend ran six 20-second saturated blocks in three balanced cycles.

| Backend | Decisions | P50 | P95 | Mean interval | Throughput | Speedup vs MLX |
|---|---:|---:|---:|---:|---:|---:|
| compiled MLX FP16 | 8,126 | 14.563 ms | 16.723 ms | 14.773 ms | 67.69/s | 1× |
| ANE FP16 | 18,729 | 6.327 ms | 7.035 ms | 6.408 ms | 156.04/s | **2.305×** |
| ANE W8 K-means | 26,102 | 4.512 ms | 5.267 ms | 4.598 ms | 217.49/s | **3.213×** |

All measured rounded outputs were stable.

## Fidelity

| Bundle | Selected-answer agreement | Max probability drift | Repeat stability | Result |
|---|---:|---:|---|---|
| FP16 L96 | 59/59 | 0.00292485 | 100/100 | PASS |
| W8 L96 | 59/59 | 0.0143929 | 100/100 | PASS |

The unchanged upstream acceptance threshold is 0.02. The four golden-fixture
questions outside the L96/K32 capacity are not included.

## Comparison with the upstream M3 Max run

Upstream sustained P50 values:

- compiled MLX: 6.937 ms
- ANE FP16: 4.976 ms
- ANE W8: 4.879 ms

Our M4 P50 values:

- compiled MLX: 14.563 ms
- ANE FP16: 6.327 ms
- ANE W8: 4.512 ms

The notable observation is not simply “M4 versus M3 Max”. The hardware is
structurally different: the upstream machine has four times the GPU-core count
and over three times the memory bandwidth of the base M4 Mac mini, while M4 has
a newer Neural Engine generation. The M4 result therefore suggests that the
relative value of ANE, especially the compressed W8 path, can be larger on a
base Mac than the upstream M3 Max numbers imply.

That explanation remains a hypothesis until energy telemetry and additional
controlled experiments are complete.

## Known platform warning

NumPy emits spurious float32 matmul floating-point warnings on this M4
environment. A standalone identity-matrix control reproduces the same warnings
while producing an exactly correct result. Laya intermediate and final arrays
were checked as finite, and the official fidelity gate passes.

We intentionally did not modify the upstream action-head implementation or
silence warnings globally for this baseline.

## Phase gate decision

**Phase 1 upstream reproduction: PASS.**

The project should proceed to:

1. M4 power/energy measurement using the upstream PSTR-only methodology.
2. ANE runtime trace/placement verification on this M4.
3. Ordinary Core ML and 421M Typed Decisions baselines.
4. Only then, 421M Typed Decisions → ANE feasibility work.

This baseline does not yet justify a claim about general task accuracy, long
context performance, or energy efficiency.
