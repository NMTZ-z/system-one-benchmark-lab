# Phase 3 Final — Jev / Laya / Published ANE Evaluation v1.0

Run completed: 2026-09-23/24 (+08:00)

## Executive summary

Phase 3 is complete.

We now have:

1. a full local 400-case / 2,000-decision Jev 1.13.0 zero-shot run;
2. a full local Laya Typed Decisions 421M specialist run;
3. full-task Core ML vs MLX parity for the same 421M checkpoint;
4. a published 322M ANE W8 short-decision performance/energy baseline;
5. an exact capacity audit showing why the public L96 ANE artifact cannot run
   the Typed Decisions quality benchmark unchanged.

The remaining question is no longer "does ANE work?" It is:

> Can a long-context 421M ANE graph preserve the 421M specialist quality while
> retaining enough of the short-context ANE speed/energy advantage to justify
> the engineering cost?

That becomes Phase 4.

## 1. Jev 1.13.0 — local zero-shot generalist

Live TypeSafe API:

- request alias: `jev-latest`
- concrete response model: `jev-1.13.0`
- 400 / 400 cases successful
- 2,000 / 2,000 decisions returned
- accuracy: **0.737**
- soft accuracy: **0.538**
- KL: 1.503
- Brier: 0.1477
- ECE: 0.0422
- Score MAE: 0.3876
- P50: 960 ms/case from this client

A 100-case immediate repeat changed 9 / 500 selected labels (1.8%), establishing
observable live-endpoint nondeterminism.

The public Sep 18 Jev result used byte-identical test data but reported accuracy
0.727. The difference is not caused by dataset drift. Run variance and/or
unversioned serving-stack behavior remain plausible contributors.

## 2. Laya Typed Decisions 421M — local specialist

MLX FP16, same public test split:

- 400 / 400 cases successful
- 2,000 / 2,000 decisions
- accuracy: **0.766**
- soft accuracy: 0.471
- KL: **0.117**
- Brier: **0.0615**
- ECE: 0.213
- Score MAE: **0.242**
- P50: 514 ms/case on the local M4

This checkpoint is a specialist fine-tuned on the benchmark-family training
split (1,200 cases / 6,000 decisions). Jev is a zero-shot generalist.

Their rows answer different questions and must not be presented as an overall
model ranking.

Descriptively, in these local runs:

- the Laya specialist has higher argmax accuracy by 2.9 percentage points;
- Jev has higher soft accuracy and lower hard-label ECE;
- Laya has much lower KL, Brier, and Score MAE against the teacher's full
  probability distributions.

Those are different properties, not a single "winner" axis.

## 3. 421M backend parity — MLX vs ordinary Core ML

Same checkpoint, same 2,000 decisions:

- selected-decision mismatches: **0 / 2,000**
- accuracy: 0.766 on both
- max probability delta: 0.0030
- max Score-value delta: 0.0039
- max Noul delta: 0.0049

Therefore the ordinary 421M Core ML conversion preserves the model's practical
decision quality.

Runtime on the five-question full benchmark:

- MLX P50: **513.7 ms/case**
- Core ML CPU+GPU P50: 887.9 ms/case
- Core ML / MLX P50: 1.73×

For this workload on the base M4, MLX is the more efficient existing 421M local
backend, primarily because MLX can exploit batching while the ordinary Core ML
B1 path executes the questions sequentially.

## 4. Published 322M ANE — what it proves

The public W8 ANE graph is a different checkpoint
(`convaiinnovations/laya-multilingual`) and a different fixed shape
(B1 / L96 / K32).

On the frozen short-decision M4 baseline:

- W8 ANE sustained interval: 4.598 ms
- 3.213× faster than the compiled MLX short-decision baseline
- gross system energy per decision: 5.820× improvement vs MLX

This is strong evidence that a graph rewritten specifically for ANE can deliver
large short-workload speed/energy gains.

It is not evidence that a long-context 421M graph will retain those gains.

## 5. Why the public ANE artifact cannot be quality-scored here

Typed Decisions unmodified prompt lengths:

- minimum: 127
- median: 323
- P95: 450
- P99: 575
- maximum: 631 tokens

Public ANE maximum length: **96**.

Capacity:

- L96: 0 / 2,000 decisions
- L192: 472 / 2,000 (23.6%)
- L384: 1,597 / 2,000 (79.85%)
- L512: 1,961 / 2,000 (98.05%)
- L640: 2,000 / 2,000 (100%)

The public L96 artifact therefore receives **no Typed Decisions quality score**.
Truncating state/instructions/criteria would change the benchmark.

## 6. Phase 3 conclusion

The evidence closes the evaluation phase:

- Jev local independent replay: complete.
- Laya 421M specialist quality baseline: complete.
- 421M MLX/Core ML parity: complete.
- public ANE performance/energy reproduction: complete.
- public ANE quality-benchmark compatibility audit: complete.

There is now enough evidence to justify a **bounded Phase 4 feasibility study**,
but not enough to justify committing immediately to a production-quality 421M
ANE port.

## 7. Phase 4 recommendation: long-context 421M ANE feasibility

Do not start by building the final L640 artifact.

Use staged shape gates:

### Phase 4A — graph feasibility

Targets:

1. L192
2. L384
3. L512

For each shape, answer:

- does Core ML conversion succeed?
- does the compute plan prefer ANE for the heavy graph?
- what is compile time?
- peak RAM / package size?
- single-question latency?
- sustained latency?
- energy per decision?
- conversion fidelity?

Stop early if the graph falls back substantially to CPU/GPU or if latency /
memory scaling destroys the short-context advantage.

### Phase 4B — useful benchmark coverage

If L384 remains technically attractive:

- run the 1,597 naturally fitting Typed Decisions decisions;
- compare decision-by-decision against 421M MLX;
- do not truncate the remaining 403 decisions.

If L512 remains attractive:

- repeat on 1,961 / 2,000 naturally fitting decisions;
- inspect the 39 over-capacity decisions separately.

### Phase 4C — full coverage decision

Only if L512 is still competitive should L640 be attempted for 100% benchmark
coverage.

This sequence avoids spending substantial engineering effort on an L640 graph
before we know whether long-context ANE placement is viable on the base M4.

## Final project state

Phase 3 status: **COMPLETE**

Next engineering gate:

> **Phase 4A — 421M Long-Context ANE Feasibility**

The existing MLX 421M backend remains the practical local baseline until that
feasibility study proves otherwise.
