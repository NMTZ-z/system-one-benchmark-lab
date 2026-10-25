# Phase 8.3 — Decision Value Evaluation Protocol v1

**Status:** protocol frozen for the bounded public replay. This is an offline Shadow experiment and historical-data audit, not a new independent blind test, not paid Provider E2E, and not an Active policy experiment.

## 1. Question, hierarchy and control

The primary question is whether **Rules + Local Typed Decision** improves *independently specified decision correctness* over **Rule-only**, at what local inference expense, on which decision opportunities, while retaining all deterministic guards. Native Agent behavior is Baseline A, but is **NOT_MEASURED** in a paired decision comparison unless original platform actions **and independent native outcome oracle** are available on the same controlled task and input. A synthetic editor-provided gold label is not a native task oracle.

- **A Native Agent**: leave Agent behavior unchanged. Independently check actual tool/file/remote state and task outcome. Native decision quality needs a separately annotated native decision; task success alone does not supply that label.
- **B Rule-only**: replay the same standardized input through the existing trusted deterministic policy and conservative fixed fallback; no model inference.
- **C Rules + Laya**: same hard rules, safe candidates and input; genuinely invoke locally cached Laya/MLX **only when eligible**. Preserve both raw and guarded recommendations. Existing Completion `0.70` safety threshold and Retry safety policy are frozen.

The same `standardized_input_sha256` identifies the per-case input for B and C. This is a *consistency marker*, not proof of source authentication; native evidence must also satisfy the Phase 8.2B independent verifier. No other decisions are made based only on matching timestamps.

### Required rules-matched Completion controls

**Re-audit finding:** the historical Phase 8B `rule_only()` comparator includes a positive verified-flags `complete` shortcut not present in production Completion `_hard_gate()`. Therefore its original B/C accuracy difference must **not** be interpreted as model incremental value.

Report both separate policy contrasts for Completion, without modifying the frozen gold or recorded inference:

- **B0/C0:** identical original seven pre-model hard rules, B0 abstains to `verify` on unresolved states, C0 retains the *observed* Laya result with unchanged safety guard.
- **B1/C1:** B1 = original Phase 8B positive-flag Rule-only replay; C1 = same B1 rule applied first, with the originally observed Laya result reused **only** for remaining unresolved states. C1 is a **counterfactual** and its hypothetical skipped local calls are not real saved compute.
- All flagged positive completions originate from *public editorial flags*, not freshly authenticated native outcomes. Never activate B1/C1 as auto-stop on this evidence.

Retry B/C already share the same deterministic rules. Aggregate scores must continue to distinguish synthetic and public-reconstruction provenance.

## 2. Datasets, labels and blinding

Keep these sources separate:

- `synthetic`: public Phase 8A Completion templates and 8C frozen Retry corpus. Gold = **synthetic_editorial**.
- `public_reconstruction`: 30 public reconstruction-style historical Completion cases; gold = **reconstruction_editorial**, **not fresh native E2E**.
- `fault_injection`: controlled defects and their independently documented fault oracle (not included in first capture).
- `real_agent`: explicitly authorized native experiments with a truly independent task/decision oracle (not included in first capture).

Published Phase 8A/8C data, including 8C's public `holdout` split, are historical **observed** samples, not a newly blinded evaluation. No model scores or safety rules may be tuned against this sample and then called blind.

The evaluator requires a freeze manifest with exact SHA-256 of (a) the captured JSONL, (b) this protocol, and (c) the evaluator source; it also records source commit and `freeze_kind`. Any edit invalidates the frozen evaluation until a separately disclosed new version. A full future blind study must freeze labeling, protocol, code and data **before** first inference on the independent holdout.

## 3. Auditable captured schema

`local-system-one/decision-value-case-v1` stores only bounded case IDs, public sample source/split, standardized-input digest, acceptable/preferred editorial or oracle labels, evaluated opportunity, Rule-only decision, Rules+Model decision, observed model attempt/completion/backend/timing, separate raw and guarded decisions, safety override and nullable native task/oracle observations.

It never exports task text, prompts, error strings, raw tools, private IDs, headers or tokens. A model failure must remain a charged attempted inference; it cannot silently become a `rule_only` model-free observation. The pure Opportunity evaluator never itself calls a model.

Independent input checks reject false Native success, duplicate IDs, unsupported model labels, model work outside eligible candidates, unvalidated hard-rule overrides, contradicted evidence, apparent zero-cost completed inference, active authority and dataset/protocol/evaluator freeze mismatches. Grouping is always **gate × source × split**.

## 4. Measures and interpretation

For each group, not pooled across provenance:

- **Opportunity coverage**, Rule-only coverage, Typed-model eligibility, actual model attempts/completions and safety overrides.
- **Decision quality**: acceptable-set accuracy; preferred-choice accuracy if adjudicated. A model's probability is not calibrated confidence.
- **Completion**: Complete precision/recall and Premature Completion on cases where Complete is not an acceptable label.
- **Retry**: policy-forbidden Retry Rate, Missed Verification Rate, Unnecessary Escalation Rate. Policy-forbidden does **not** mean proven physical harm.
- **Performance**: measured local model-path P50/P95 and sample counts; suppress broad performance claims for small n. Shadow overhead is not Native task-time savings.
- **Native**: native independently observed task successes, independently adjudicated native choice quality if available, and externally capped Provider attempt counts if actually witnessed. Unknown fields stay null.
- **Economics**: native token and billing counts only with trustworthy Provider/invoice evidence; no available evidence ⇒ UNKNOWN. Shadow-only actual API savings = **NOT_MEASURED**, even if a counterfactual replacement looks promising.

A full Native comparison requires exact authenticated causal linkage, matched tasks, controlled requests, no state leakage, isolated disposable profiles and independent oracle checks. A successful public structural replay is not a real Provider E2E.

## 5. Safe execution and future evidence gates

No real StepFun request or new paid Provider without a separately stated maximum **physical attempts, wall time, subscription/API budget and explicit approval**. Use a disposable profile, isolated repository and enforced local proxy; no production Hermes/DSH configuration or irreversible actions. If no authorizing budget is available, Native Real Provider Validation is **BLOCKED**, not Mock-PASS.

The first capture uses a locally cached Laya Typed Decisions 421M checkpoint with MLX, **zero paid main Provider calls**, no Native Agent. Decision identity (`laya-typed-decisions@f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`) is distinct from observed local execution backend (`mlx`). Checkpoint startup temperature-clamping warning makes affected confidence **uncalibrated**.

Reproduce from project root with its existing Python environment:

```bash
python -m benchmarks.decision_value.capture \
  --source /path/to/verified/locally/cached/laya-typed-decisions \
  --output benchmarks/decision_value/fixtures/phase8_3_public_replay.jsonl

python -m benchmarks.decision_value.evaluate \
  --dataset benchmarks/decision_value/fixtures/phase8_3_public_replay.jsonl \
  --manifest benchmarks/decision_value/fixtures/phase8_3_public_replay.freeze.json \
  --protocol docs/PHASE8_3_EVALUATION_PROTOCOL.md \
  --output results/processed/phase8_3_decision_value.json
```

Re-capturing the local model may change timings and invalidates the existing freeze digest. For exact frozen-results verification, use the **committed** capture/manifest unchanged. No model download, external API or subscription billing is required to verify committed replay results.
