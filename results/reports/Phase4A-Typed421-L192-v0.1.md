# Phase 4A — Typed Decisions 421M ANE L192 v0.1

Run date: 2026-09-24 (+08:00)

## Gate

**PASS.**

The Laya Typed Decisions 421M checkpoint can be rewritten as the same fixed-shape
BC1S/Conv ANE body used by the published multilingual ANE research path at
**B1 / L192 / K32**.

On the base M4 Mac mini:

- the complete 28-layer body converts successfully;
- all attributed nonconstant operations are preferred on the Neural Engine in
  the Core ML anticipated compute plan;
- the FP16 conversion passes the upstream conversion-fidelity gate on every
  reference question that fits L192;
- repeated rounded public results are stable.

This establishes long-context 421M ANE feasibility at L192. It does **not** yet
establish a useful end-to-end speedup over MLX for the public benchmark.

## Fixed checkpoint

- model: `convaiinnovations/laya-typed-decisions`
- revision: `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`
- weights SHA-256:
  `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e`

Architecture:

- hidden size: 1024
- encoder layers: 28
- attention heads: 16
- FFN intermediate size: 2624
- sliding-attention window: 128
- Typed Decisions vocabulary: 50,368

The non-embedding checkpoint parameters are approximately 369.7M. This is
roughly 2.95× the non-embedding parameter count of the 322M multilingual
checkpoint used by the published ANE bundle.

## Single-layer preflight

Before converting the complete body, one representative L192 encoder layer was
rewritten and converted.

| Metric | L192 layer |
|---|---:|
| Preferred ANE operations | **368** |
| Preferred CPU/GPU operations | **0** |
| Estimated attributed cost on ANE | ~100% |
| P50 | 2.372 ms |
| P95 | 2.869 ms |
| PyTorch layout max error | 2.67e-5 |
| Core ML max absolute error | 0.0710 |
| Core ML RMSE | 0.00302 |

The Core ML numerical error is not anomalous relative to the upstream 322M
research layer: that layer's reported max absolute error was 0.1496 with RMSE
0.00392.

## Full-body conversion

The full fixed L192 body contains the embedding norm, 28 encoder layers,
decision head, scorer and CLS output. Token embedding lookup and the small
action head remain on the host.

| Metric | 421M L192 |
|---|---:|
| Package size | **741,741,391 bytes (~707 MiB)** |
| Core ML conversion | **155.35 s** |
| First load + AOT compile | **158.41 s** |
| Preferred ANE operations | **10,594** |
| Preferred CPU/GPU operations | **0** |
| ANE-supported operations | 10,594 |
| Estimated attributed cost on ANE | ~100% |
| Body mean | 32.74 ms |
| Body P50 | **32.14 ms** |
| Body P95 | 47.74 ms |
| Body P99 | 48.35 ms |

The `unknown` operations in the plan are constants / unattributed operations;
all 10,594 attributed nonconstant operations are preferred on
`MLNeuralEngineComputeDevice`.

The compute-plan result is anticipated-placement evidence, not a hardware trace.

## Golden fidelity

The existing upstream `laya-typed-decisions` FP32 reference set contains 16
cases. Fifteen fit the L192 fixed shape; the L1024 case is intentionally
skipped.

| Gate | Result |
|---|---:|
| Reference cases evaluated | 15 / 16 |
| Questions evaluated | 60 |
| Argmax agreement | **60 / 60** |
| Max calibrated probability error | **0.00640** |
| Max action-probability error | **0** |
| Repeat calls | 100 |
| Repeated rounded public results identical | **yes** |
| Gate threshold | 0.02 |
| Result | **PASS** |

Maximum raw decision-logit error was 0.0746.

The host action path emitted numerical overflow/divide warnings for some
saturated cases. The checkpoint's own FP32 golden action logits can reach about
±5,000. Despite raw action-logit drift up to 64.1 in one case, the action
probability remained identical to the golden result for all evaluated
questions. This is recorded as a host-path numerical-stability note rather than
an ANE fidelity failure.

## End-to-end short1 observation

With the fixed L192 graph:

- P50: **50.05 ms**
- P95: 52.74 ms
- P99: 54.59 ms

This is **not** an apples-to-apples speed comparison against the Phase 2 MLX
one-question result. The ANE graph always computes the full L192 shape, while
the short MLX prompt is materially shorter.

The result therefore must not be described as "ANE is slower than MLX" or
"ANE is faster than MLX" for matched L192 workloads. A length-matched comparison
is still required.

## Benchmark capacity

For the unmodified public Typed Decisions prompts:

- L192 naturally fits **472 / 2,000 decisions = 23.6%**.

This figure is a capacity result, not a quality score.

## Engineering observations

The full 421M graph is materially heavier than the published 322M ANE graph.

The research package also has a substantial first-use AOT compile cost on this
base M4. The original upstream probe obtains a compute plan by loading the
compiled model again, which triggers another expensive AOT path for this large
graph. Future L384/L512 experiments should avoid recomputing a plan unless the
placement evidence is needed for that gate.

Research `.mlpackage` files are intentionally excluded from Git. The compact
summary, manifests, validation output, and reports remain versionable.

## Decision

Proceed to **L384**.

L192 passes the structural, placement, fidelity, and repeatability gates. The
next question is whether long-context scaling remains useful:

> Does L384 preserve ANE placement and fidelity while providing enough runtime
> advantage on genuinely long prompts to justify the larger fixed shape?

No L512/L640 conclusion is made from the L192 result.
