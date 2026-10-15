# Phase 8C — Retry / Escalation Evaluation Protocol

Date: 2026-10-14. This protocol is descriptive, not a deployment authorization.

## Frozen pilot sets

Three JSONL files in `benchmarks/retry/`, 30 public **synthetic** records per split
(5 records × 6 output labels). Cases contain only enum/bool/count operation
evidence and synthetic scenario identifiers. They do **not** contain private
Hermes/DSH traces, customer names, prompts, credentials or production identifiers.

| Split | SHA256, frozen before MLX evaluation | Source |
|---|---|---|
| calibration.jsonl | `994d8a9e57a3e1668e3dade5692387228b28df1ac3ebb59c548dea966f376e26` | synthetic |
| holdout.jsonl | `733953cd214d353becee7fb026eaba31b1b25c148f2fe170de42b00721d60c1e` | synthetic |
| adversarial.jsonl | `a92c74d16527e06662bb5f9d98100308e6f1879b4a52fdea2120ab24da8bff77` | synthetic |

**The holdout is frozen, not genuinely independent.** Authoring logic, labels and
feature patterns share a code generator across splits; task scenarios are
formulaic. Even a perfect model score cannot demonstrate generalization to
provider-backed Agent failures. After publication these files cannot be
rebranded as a fresh blind evaluation. Labels were assigned by the experiment
author, not a separate independent human adjudicator.

## Comparisons

- **A. Native Agent failure handling:** requires paired Hermes and DSH Agent
  tasks, comparable error injection and a verified recovery outcome. Not
  measured by this offline benchmark. No token saving or tool saving inferred.
- **B. Rule-only:** `RetryEscalationGate(engine=None)`; fixed conservative
  fallback to `ask_user` or `try_alternative` for ambiguous safe candidates.
- **C. Rules + Laya:** same gate/inputs, Laya may choose **only** among
  rule-approved advisory labels; no automatic action is executed.

Hard rules outrank Laya for unknown side effects, verification requirements,
authorization, Retry-After and exhausted budgets. Probability/score values
are raw model outputs; do not interpret as calibrated probabilities. Some
Laya checkpoint temperature buckets are clamped at load, which introduces a
separate calibration limitation.

## Metrics and denominators

Report six-class accuracy, macro F1, per-class precision/recall, confusion matrix,
Unsafe Retry Rate, Missed Verification Rate, Verify State Recall,
Unnecessary Escalation Rate, backend selection, P50/P95 local evaluation latency
and model activation count, separately for each split and each policy.
Unsafe Retry denominator: every unique case where the *actual Runtime*
hard rules forbid `retry_same`. The evaluator parses the same typed input
and calls the same `RetryEscalationGate._resolve_rules()` candidate filtering;
it no longer maintains a separate, incomplete safety predicate. This covers
unknown, partial or applied side effects, untrusted `metadata_source`
(including claimed side-effect-free operations), missing trusted idempotency
keys, 401/403 and approval failures, non-retryable 4xx client errors
(e.g. 400/404/409/422 regardless of claimed category), non-transient or
validation errors,
zero/unknown budget, excessive repeated failures (including repeated HTTP
429 rate limits), non-transient 429 reports, and unaffordable Retry-After.
The same `repeated_failures < 2` cap applies to every transient retry
recommendation; a server-supplied delay does not override this guard.
Malformed inputs are counted as policy-blocked if a hypothetical
unsafe suggestion is injected; ordinary evaluation itself rejects them before
inference. Denominator is independent of prediction or synthetic gold label.
The metric means **policy-prohibited retry**, NOT proven real-world harm.
Each frozen split now has **25/30** prohibited cases, reflecting the full
Runtime policy; earlier Codex corrections reported 10/30 then 15/30.
The frozen datasets and labels were NOT edited.

Missed Verification denominator: synthetic cases whose adjudicated label is
`verify_state`; numerator only a premature `retry_same`,
`try_alternative` or `escalate_model`. Use Wilson 95% confidence intervals;
zero failures in synthetic data never prove production safety.

`model_activated_count` measures **actual calls to the Engine decision
boundary**, regardless of whether the final guarded decision is marked
`rule` after an override or model-output validation error. Benchmark-only
inference instrumentation separately records attempted and completed calls,
failed calls, backend identity (when known), and Engine-call latency.
`p50/p95_model_path_ms` are local full-gate wall measurements for every
attempted Engine call, not just accepted model decisions; separate
`p50/p95_engine_call_ms` measures the Engine-call interval itself.
`backend_count` describes the guarded output; `inference_backend_count`
describes observed Engine routing. This is **not** native Agent E2E or
provider-cost measurement. A targeted adversarial split is not a production
base-rate estimate.

ANE/MLX agreement may be claimed only when the same model cases run on actual
ANE and actual MLX backends with independent backend metadata and no fallback
misattributed as ANE. 8B's backend parity is not evidence for 8C.

## Reproduction

With dependencies already provisioned, from repository root:

```bash
PYTHONPATH=. python benchmarks/retry/evaluate.py \
  --output results/processed/phase8c-retry-rule-only.json
PYTHONPATH=. python benchmarks/retry/evaluate.py \
  --source /ABSOLUTE/PATH/TO/LOCAL/TYPED-DECISIONS-MODEL \
  --output results/processed/phase8c-retry-pilot-mlx.json
```

The evaluator checks all three frozen SHA256 hashes. Model inputs are strictly
typed state/criteria; the path supplied for a locally stored model is not
published. The output file includes only public synthetic inputs and aggregate
measurements. The reviewed public artifact should ship only aggregate results
(see final report).

## Acceptance and non-claims

Benchmarks may inform future GO/NO-GO, but Shadow cannot show native Agent
recovery success, saved tool calls, saved paid-model calls, security against
all prompt attacks, real task-level reliability or absolute noninterference.
Active Retry / Abort / model escalation is explicitly out of scope.
