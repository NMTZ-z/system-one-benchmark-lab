# Phase 8.3 — New Preregistered Synthetic Holdout Pilot v1

**Date: 2026-10-20. Status: OFFLINE / SHADOW PILOT COMPLETED. No Native Agent task execution; Active remains NOT_AUTHORIZED.**

## Bottom line

On **80 newly authored synthetic/fault-injection cases**, preregistered in
Git **before model inference**, Completion Rule-only and guarded
Rules + Laya **tied** at 30/40 acceptable decisions (75%). On Retry/Escalation,
Rule-only reached 36/40 (90%) and Rules + Laya reached 40/40 (100%).
The Retry improvement was **4 additional correct recommendations, zero
model-only regressions among these particular fixtures**.

This supports further investigation of small-model classification in *bounded
Retry scenarios*. **It does not establish general-purpose real Agent value,
production accuracy, reduction in API calls, or permission to run Active
Retry, Completion, or paid escalation.** Synthetic gold and candidate safety
metadata were authored by the same team that built the evaluation. The set is
new and preregistered, but it is **not an external independent adjudication or
a randomly sampled operational task population**.

## 1. Preregistration integrity and run identity

| Property | Evidence |
|---|---|
| New case count | 80: 40 Completion, 40 Retry/Escalation |
| Distinct authored scenario families | 80 |
| Synthetic sources | Completion: synthetic editorial; Retry: controlled fault-injection oracle |
| Previous public input collision | 0 exact matches to old Phase 8A Completion and 8C Retry public source corpora |
| Gold | Preferred decision and allowed decision set, each with a prior-to-inference simulated oracle rationale |
| Dataset SHA-256 | 456326d1962b915aa1cb4db1df00831a7c14b9503dc11a5c81df9a08e1a491d8 |
| Git commit sealing data, labels, runner, protocol and relevant policy source | 1245a3cb17120f0f6bee198a34aa159ea3eeb851 |
| Prereg protocol | docs/PHASE8_3_NEW_HOLDOUT_PROTOCOL.md |
| Local decision model | Laya Typed Decisions 421M; source revision f9ab0b228f0fc0f14d873dbc99038f135c2da1b2 |
| Execution backend | Local MLX, no ANE path for this study |
| Main Provider requests | **0** |
| Actual Native Agent outcomes | **NOT_MEASURED** |

The runner explicitly verifies archived bytes at that frozen Git commit
and rejects a changed manifest, case file, runner, protocol or frozen Gate
policy. The case registry was sealed **before** calling the local model.
Every expected case remains in the published capture; there were no skipped,
relabelled or deleted low-scoring records.

The frozen fixture file contains **only fabricated public data**. Its
synthetic gold labels and the text describing the scenario oracle are not
passed to the local model; it receives the normalized case inputs.
Exact non-duplication is a limited mechanical guarantee, **not** proof of
semantic novelty, independence from model pretraining, or nonoverlap of
underlying problem families.

## 2. Fair paired comparisons

B0 and C0 used precisely the **same existing hard-rule predicates**.
Completion uses the production seven-rule checks, then B0's conservative
verify fallback or the original Completion Gate for C0 with its **unchanged
0.70 complete guard**. Retry uses the same recovery policy and bounded
candidate set; only non-deterministic remaining cases reach Laya.

| Preregistered cohort | Cases | Rule-only correct | Rules + Laya correct | Actual model invocations | Model safety overrides |
|---|---:|---:|---:|---:|---:|
| Completion / synthetic | 40 | 30/40 (75%) | 30/40 (75%) | 15/15 completed | 14 |
| Retry / fault-injection | 40 | 36/40 (90%) | 40/40 (100%) | 14/14 completed | 0 |
| **Sum, for work accounting only** | **80** | **Do not pool accuracy** | **Do not pool accuracy** | **29/29 completed** | **14** |

### Where the difference came from

**Completion:** 25/40 cases were resolved by the existing hard rules.
On the 15 eligible model cases, **both B0 and C0 got 5/15 acceptable
choices**. Laya emitted raw complete in 14 cases, which the unchanged
safety guard reduced to verify. Neither B0 nor C0 recommended complete
on this held-out cohort: observed premature completion is 0, but recall
for true completed cases is also **0**. A zero false-stop count alongside
zero completed-task recognition is not a production safety validation.

**Retry:** 26/40 cases were resolved without model inference. On the
14 remaining opportunities, Rule-only was acceptable on 10/14 and
Rules + Laya was acceptable on 14/14. Four Rule-only conservative
ask_user suggestions were replaced by allowed retry_same recommendations,
all in synthetically trusted read/verified-nonexecution scenarios.
Four additional **correct** recommendations does not establish that retry
executions would have been safe or beneficial in a real system. On the
33 policy-forbidden retry cases, both arms returned **0 policy-forbidden
retry_same choices**. This is a policy-label result, not a measured
real-world harm rate.

### Paired discordance and small-N limitations

| Cohort | Both correct | Rule-only alone correct | Model alone correct | Neither correct |
|---|---:|---:|---:|---:|
| Completion, 40 | 30 | 0 | 0 | 10 |
| Retry, 40 | 36 | 0 | 4 | 0 |

An illustrative exact paired sign/McNemar comparison for four one-way
Retry disagreements gives two-sided p = 0.125. This is **not** a
confirmatory significance test: author-crafted scenario cases are not
a representative random sample and exhibit policy-construction bias.
In particular, the **100% synthetic Retry accuracy is a validation
limitation, not a production performance promise**.

Acceptable-label accuracy permits more than one recommendation for some
cases. Preferred-choice accuracy is 75% in Completion for both arms, and
82.5% vs 97.5% in Retry for B0 vs C0.

## 3. Actual compute, guarded policy and cost

| Split | Measured local MLX call N | P50 | P95 |
|---|---:|---:|---:|
| Completion | 15 | 64.297 ms | 122.436 ms |
| Retry | 14 | 62.254 ms | 65.984 ms |

These are measured local Engine-call timing, **not native Agent wall-time
overhead**, not billed token usage and not a production P95 estimate.
The upstream model emitted a checkpoint temperature-clamping warning;
confidence in affected buckets is not calibrated. There is no MLX vs ANE
comparison in this study.

- Physical main-Provider requests in this replay: 0 (no real StepFun run).
- Native main-model token accounting: UNKNOWN / NOT_MEASURED.
- Subscription billing reduction: NOT_MEASURED.
- Real Agent task completion delta: NOT_MEASURED.
- Actual removed local Laya calls by an alternative policy: NOT_MEASURED.
- No dynamic gate, dispatch, model hot switch, retry execution or file mutation
  was authorized or implemented.

## 4. Separate, exploratory dataset-quality check

**Not preregistered and not the B0/C0 headline:** the older Phase 8B
positive-verified-flags Completion shortcut produced 40/40 correct
decisions on this author-designed simulation. That suspiciously perfect
fit shows the current fixtures may reward a rule already known during
construction. It must **not** be retroactively adopted as the new
primary comparator, tuned, or turned into an Active completion policy.
It does motivate collecting externally independently verified, conflicting
flag cases.

A good next real-data experiment should include optimistic/incorrect Agent
self-reports, delayed and partially applied operations, ambiguous native
event coverage and verification outcomes that cannot be deduced from an
editorial boolean flag.

## 5. Reproduction without repeating model inference

- Prereg case generator: benchmarks/decision_value/holdout_v1/build_frozen.py
- Frozen cases and manifest: benchmarks/decision_value/holdout_v1/new_frozen_holdout_v1.jsonl and new_frozen_holdout_v1.freeze.json
- Preregistered runner: benchmarks/decision_value/holdout_v1/replay.py
- Captured evaluated decisions: benchmarks/decision_value/holdout_v1/observations_v1.jsonl
- Published grouped report: results/processed/phase8_3_new_holdout_v1.json
- Independent code and evidence regression: tests/test_phase8_3_new_holdout.py and tests/test_phase8_3_new_holdout_frozen.py

The captured JSONL and grouped report allow a deterministic **read-only**
rescore. Re-running the Laya experiment is **not needed** to verify the
results and must not be used to select a better sample of predictions.

## 6. Final acceptance

| Dimension | Decision |
|---|---|
| Preregistration order, hash and case completeness | **PASS** |
| New offline Shadow paired B0 vs C0 | **PASS, synthetic scope** |
| Completion Laya advantage on this cohort | **NOT ESTABLISHED** |
| Retry Laya incremental benefit on this cohort | **OBSERVED, LIMITED** |
| External independent real task evidence | **NOT ESTABLISHED** |
| Native StepFun + Laya post-8.2B requalification | **BLOCKED, no approved Provider budget** |
| Agent-level token/time/billing saving | **NOT MEASURED** |
| Active readiness | **NOT AUTHORIZED** |

Next: keep PR #9 a draft and complete independent review. Only then, with a
separate, explicit physical-request/time/billing cap, run isolated native
StepFun Step 5 Preview + Laya Shadow tasks on Hermes and DSH. Choose
verification oracles independently of the Agent's final text.
Do **not** interpret this offline scoring exercise as sufficient grounds
for a production Canary or a new Action Risk Gate.


## 7. Final regression and publish gate

Validation stance: **share with caveats**, not ready for a production
decision. Verified after original preregistration and the one local
model run: **Python 1008/1008 PASS** (including original Gate and Hermes
tests, frozen-file tamper checks and the 80-case replay audit),
**DSH Vitest 64/64 PASS**, **TypeScript typecheck PASS**, **DSH build PASS**.

The public release allowlist and privacy sanitizer must succeed on
the final clean committed tree. Case inputs are deliberately fabricated;
the public observations contain only normalized decision labels,
probabilistic classification metadata and timing/digest fields.
No private native trace, real task content, API key, provider receipt,
HMAC key, full external request or true user file path is committed.

**Unresolved blocker** for next-stage value validation:
independently adjudicated real Agent cases with audited native event
provenance, plus explicit paid StepFun request/time/expense cap. The
mock/fault-injection gold is insufficient to claim real-world safety.

## 8. Local checkpoint fingerprint (post-run provenance)

The local cached HF snapshot used by the completed replay has these observed
SHA-256 file digests (collected after the one-shot replay):

- model.safetensors:
  4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e
- rl_agent_config.json:
  ebf0cd524d92342a6be5e48e9fca3d7c2babfb5a56ccd79d2171ef5d8c7f7be8

The model repo/revision had been preregistered, and the runner required that
exact locally cached revision. These post-run hashes improve reproducibility
but are **not themselves evidence of a before-and-after checkpoint integrity
attestation**. They do not certify model authorship, quality, license
compatibility or that any real Agent operation used this checkpoint.
