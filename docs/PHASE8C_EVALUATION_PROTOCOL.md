# Phase 8C — Retry / Escalation Evaluation Protocol

Date: 2026-10-14. This protocol is descriptive, not a deployment authorization.

## Frozen pilot sets

Three JSONL files in \`benchmarks/retry/\`, 30 public **synthetic** records per split
(5 records × 6 output labels). Cases contain only enum/bool/count operation
evidence and synthetic scenario identifiers. They do **not** contain private
Hermes/DSH traces, customer names, prompts, credentials or production identifiers.

| Split | SHA256, frozen before MLX evaluation | Source |
|---|---|---|
| calibration.jsonl | \`994d8a9e57a3e1668e3dade5692387228b28df1ac3ebb59c548dea966f376e26\` | synthetic |
| holdout.jsonl | \`733953cd214d353becee7fb026eaba31b1b25c148f2fe170de42b00721d60c1e\` | synthetic |
| adversarial.jsonl | \`a92c74d16527e06662bb5f9d98100308e6f1879b4a52fdea2120ab24da8bff77\` | synthetic |

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
- **B. Rule-only:** \`RetryEscalationGate(engine=None)\`; fixed conservative
  fallback to \`ask_user\` or \`try_alternative\` for ambiguous safe candidates.
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
Unsafe Retry denominator: unknown/partial/applied side effects or a blocked
authorization/retry budget. Missed Verification denominator: synthetic cases
whose adjudicated label is \`verify_state\`; numerator only a premature
\`retry_same\`, \`try_alternative\` or \`escalate_model\`.
Use Wilson 95% confidence intervals. A zero count with a small denominator
does **not** prove safety. A targeted adversarial split is not a production
base-rate estimate.

ANE/MLX agreement may be claimed only when the same model cases run on actual
ANE and actual MLX backends with independent backend metadata and no fallback
misattributed as ANE. 8B's backend parity is not evidence for 8C.

## Reproduction

With dependencies already provisioned, from repository root:

\`\`\`bash
PYTHONPATH=. python benchmarks/retry/evaluate.py \
  --output results/processed/phase8c-retry-rule-only.json
PYTHONPATH=. python benchmarks/retry/evaluate.py \
  --source /ABSOLUTE/PATH/TO/LOCAL/TYPED-DECISIONS-MODEL \
  --output results/processed/phase8c-retry-pilot-mlx.json
\`\`\`

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
