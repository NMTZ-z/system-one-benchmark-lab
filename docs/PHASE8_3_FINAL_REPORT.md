# Phase 8.3 — Decision Opportunity & Value Validation

**Checkpoint: 2026-10-20. Status: OFFLINE ENGINEERING ACCEPTANCE (LIMITED). Paid Native StepFun requalification BLOCKED. Active NOT AUTHORIZED.**

## Executive finding

**The value of a local Typed Decision model depends on the Gate and available evidence.** On 210 previously published public/historical case replays (including 30 public-reconstruction Completion cases), 109 actual Laya 421M MLX Engine calls completed. On this particular sample, Rules + Laya materially improved synthetic Retry/Escalation decisions over Rule-only.

**Post-implementation audit correction:** the original Completion comparison was not rules-matched. Its Rule-only policy had an extra favorable-flag `complete` heuristic, absent from the model-first branch. The originally quoted Completion accuracy loss is therefore **not evidence of a causal Laya disadvantage**. Matched, retrospective Completion controls are reported below without changing the original dataset or any Gate. We did not change the existing Completion threshold or Retry safety policy to make the results look better.

These results are **not** a new independent blind study, native Agent successes, verified Provider token savings, or paid StepFun E2E evidence. The actual Agent-level benefit remains **NOT_MEASURED**.

## 1. Baseline, repo separation and revision evidence

| Item | Verified state |
|---|---|
| GitHub public `main` on 2026-10-20 | `062d52e753e7e00d91a536dc81e9d85b8819cb12` (PR #8 Phase 8.2B merged) |
| GitHub open PRs at kickoff | 0 |
| Local NAS Forgejo development checkout `main` | `afa2512cc66400d111c28cb5fe00e9f83fdba49a` |
| Relation between local NAS main and GitHub main | Local NAS head was **not** confirmed an ancestor of GitHub `main`. Do not merge or overwrite it blindly |
| Isolation | New dedicated worktree `~/Projects/system-one-phase8-3`, branch `feat/phase8-3-decision-value`, starting from the exact public main SHA |
| Production Hermes/DSH configuration | Unchanged |
| Laya model identity | `convaiinnovations/laya-typed-decisions`, revision `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2` |
| Actual compute backend | Local Apple Silicon **MLX**, not ANE; Native main-model Provider was not invoked |

The local working checkout remains separate from the GitHub feature branch. No force push or automatic merge is authorized.

## 2. Evidence and runner audit: 8.3A

Reused existing 8.2A native runner, private independent task verifiers, 8.2B exact-correlation Evidence Contract, budget reservation ledger and isolated Provider proxy. Existing Phase 8B Completion and 8C Retry benchmark code supplies frozen gold/public policy-replay baselines. Model Backend Pilot remains independent from execution/permission authority.

8.2A historically achieved bounded **real StepFun** Agent E2E; 8.2B then proved 7 controlled native Mock executions, 9 real native tool calls and 14/14 exact correlation records. However, 8.2B's new code used a **Mock main Provider and Mock local decision Runtime** in those native tests. Old real-provider evidence cannot certify the merged new source.

**Phase 8.3A Native Real Provider Validation: BLOCKED.** No explicit count/time/paid-budget allocation was provided for a fresh StepFun `stepfun/step-5-preview` experiment. We therefore made **zero** new real StepFun requests. No claim of repaired provider linkage or native end-to-end token/billing observability is made. No second paid Provider was substituted.

## 3. Delivered Opportunity Contract: 8.3B

`local_system_one/decision_opportunity.py` implements the strict `local-system-one/opportunity-v1` advisory schema, reusing 8.2B conditional capability declarations and strict metadata-only inputs.

1. `rule_only`: reliable, adapter-policy-verified deterministic outcome.
2. `typed_model_candidate`: evidence adequate, safe stable bounded candidate set, neither planning nor Active authorization.
3. `native_agent`: new generation or deeper native planning needed.
4. `unsupported`: missing/ambiguous/untrusted evidence, capability gap, unsafe candidate or unstable options.

`retry_same` and `escalate_model` require independently prechecked policy eligibility; the model itself cannot grant permission, decide idempotency or bypass a budget. `authority.mode=shadow` and `action_allowed=false` are enforced. Any source authenticity still depends on the native 8.2B independent collectors; static schema validation alone cannot authenticate observed events or human-adjudicated labels.

No Adapter Contract v2, new runtime Gate, scheduler, Provider, dynamic switching, background service, production config or active action was introduced.

The original Phase 8.2A historical-source regression test now explicitly permits this **one new pure offline** `local_system_one/decision_opportunity.py` path in its post-8.2A changed-file allowlist. Original native Gate / Runtime operational source SHA checks remain unchanged; no broad allowlist weakening was applied.

## 4. Paired benchmark: 8.3C

Sources: the **already-public** 120-case Phase 8A Completion gold corpus (90 synthetic, 30 public-reconstruction) and the **previously frozen/published** 90-case Phase 8C Retry corpus (30 each calibration, historical holdout and adversarial). All 210 cases are *previously observed*. "Real" in the old Phase 8A public gold has provenance `public_repo_reconstructed`; this report conservatively uses `public_reconstruction`, **not** `real_agent`. No new blind holdout was generated.

Baseline B uses the Phase 8B Completion conservative Rule-only replay policy or existing Retry Gate policy. Candidate C uses identical source inputs with actual locally cached Laya/MLX inference. **For Completion, B includes a positive `required_checks_completed=True AND final_state_verified=True → complete` heuristic that is NOT present in C's actual pre-model rules.** The original B/C columns below are historical descriptive outputs, **not a rules-matched causal contrast**. For Retry, the two pipelines share the same `_resolve_rules` predicate. Native Baseline A has no paired independently verified Agent outcome in these samples, so it remains unknown, not magically filled from the Agent final response.

| Gate / source / split | N | Rule-only | Typed opportunities / actual MLX calls | B acceptable accuracy | C acceptable accuracy | Safety overrides |
|---|---:|---:|---:|---:|---:|---:|
| Completion, public reconstruction | 30 | 16 | 14 / 14 | 73.33% | **63.33%** | 10 |
| Completion, public synthetic | 90 | 40 | 50 / 50 | 88.89% | **63.33%** | 30 |
| Retry, synthetic calibration | 30 | 15 | 15 / 15 | 66.67% | **100%** | 0 |
| Retry, synthetic historical holdout | 30 | 15 | 15 / 15 | 66.67% | **100%** | 0 |
| Retry, synthetic adversarial | 30 | 15 | 15 / 15 | 66.67% | **93.33%** | 0 |
| **Separated totals** | **210** | **101** | **109 / 109** | **Do not pool** | **Do not pool** | **40** |

These are *editorial-label accuracy rates* in retrospective public corpora. The difference between two policies is **not** real-world generalization or statistically established agent value. The Completion B/C numbers above are additionally **confounded by unequal rule sets**.

### Completion: rules-matched secondary controls (correction)

An independent re-check of the existing frozen capture discovered **33/120 Completion cases** (30 synthetic, 3 public reconstructions) where the extended Rule-only heuristic returned `complete`, while the actual Completion Gate still invoked Laya and guarded to `verify`. The source code makes this discrepancy explicit: `benchmarks/completion/phase8b_offline.py::rule_only()` has a favorable-flag shortcut that `local_system_one/workflows/completion_gate.py::_hard_gate()` does not.

For a valid paired analysis we provide **two separately named rule sets**, with the original recorded model recommendations preserved and *no model re-training, new gold labels or threshold changes*:

| Rules-matched Completion contrast | Synthetic N=90 | Public reconstruction N=30 | Inference status |
|---|---:|---:|---|
| Shared pre-model hard rules + conservative `verify` (B0) | 55.56% | 63.33% | Offline replay |
| **Same pre-model hard rules** + Laya (C0) | **63.33%** | **63.33%** | Originally observed Laya decisions |
| Extended positive-flag Rule-only heuristic (B1) | 88.89% | 73.33% | Offline replay |
| **Same positive-flag heuristic first** + residual Laya (C1) | **96.67%** | **73.33%** | **Counterfactual policy replay, not actually executed as C1** |

The C1 counterfactual reuses **already captured** Laya recommendations only where B1 would abstain/leave multiple choices, and deterministically skips hypothetical inference in the 33 favorable-flag cases. This suggests **76 rather than 109 local calls** across all 210 public replay cases *if that experimental policy had actually been deployed*. **No calls were actually saved in the completed capture, and no main-model or Agent-level savings were measured.**

Neither `required_checks_completed` nor `final_state_verified` in these public editorial fixtures authenticates the correctness of a real external task. **Do not install B1 as an Active auto-completion rule.** The 0.70 Completion confidence guard remains unchanged. Forty originally observed raw `complete` choices were guarded to `verify`; this observed 40 is not the same denominator as the 33 unmatched positive-rule shortcuts.

**Corrected interpretation:** on previously known synthetic Completion scenarios, model residual classification offers a limited 7.78 percentage-point uplift with rules genuinely matched. On the 30 public-reconstruction cases it provides **no observed extra accuracy**. No independent native E2E benefit is established. Test on new, independently verified tasks before prioritizing Completion delegation.

### Retry/Escalation analysis

Actual model participation was 15/30 on each previously public synthetic split; the remaining cases were deterministic rules. The synthetic policy-forbidden Retry Rate and Missed Verification Rate are 0 in both B and C within the present scenarios. This is **not** an estimate of physical harm probability or production retry safety. The observed improvement on repeated known synthetic patterns warrants new independent cases with multiple acceptable actions, side-effect ambiguity, permission failures and genuinely unknown outcomes.

### Input freeze and evaluator

- `benchmarks/decision_value/capture.py` uses current Gate and benchmark code for frozen-public **offline** recording, storing only bounded labels, evidence, statuses, timings and one SHA-256 digest per *public* standardized input.
- `benchmarks/decision_value/evaluate.py` rejects duplicate case IDs, invented native outcomes, false inference accounting, malformed candidates, rule bypass, disallowed Active authority, contradictory gold/provenance and digest changes. It separately reports the **actual historic** B/C decision policies and the **rules-matched** Completion B0/C0 and B1/C1 counterfactuals; it never pretends counterfactual skipped calls happened.
- Captured JSONL plus freeze manifest are published at `benchmarks/decision_value/fixtures/phase8_3_public_replay.*`. The freeze pins **dataset, protocol, and evaluator source SHA-256** with the source baseline commit and model/backend identity.
- Public machine-readable aggregate: `results/processed/phase8_3_decision_value.json`. No private logs or task bodies are exported by the 8.3 capture.
- Editing a pinned source, labels or evaluator invalidates the old freeze instead of quietly changing a reported score.

## 5. Cost, runtime and resource observability: 8.3D

New requests to paid main Provider: **0**. Laya MLX Engine calls **109 attempted / 109 completed**. Local model path captured individually, without a claim of production end-to-end overhead or power consumption.

| Split | Inference samples | Local MLX call P50 | P95 |
|---|---:|---:|---:|
| Completion reconstruction | 14 | 49.553 ms | 63.734 ms |
| Completion synthetic | 50 | 49.194 ms | 51.120 ms |
| Retry calibration synthetic | 15 | 60.701 ms | 160.498 ms |
| Retry historical holdout synthetic | 15 | 60.162 ms | 62.314 ms |
| Retry adversarial synthetic | 15 | 60.301 ms | 66.778 ms |

Local model timings depend on cache and environment; 14/15 inference-call groups are especially small and cannot support broad latency claims. One calibration split includes a noticeably slower high-tail call. We have **no** paired Agent wall-time overhead estimate, energy measurement, invoice data or Provider-confirmed token count for 8.3. The Laya checkpoint emitted an upstream temperature-clamping warning, so model confidence is **uncalibrated** in affected buckets. No ANE-vs-MLX parity result is claimed for this phase.

- Shadow-only actually saved Provider calls: **NOT_MEASURED**.
- Agent task success delta: **NOT_MEASURED**.
- Billing/subscription debits: **UNKNOWN**, not automatically zero just because no directly billed API was observed.
- Potential model delegation benefit: **hypothesis to test under future expressly authorized, controlled Canary**, not a measured outcome.

## 6. Engineering regression, privacy and compatibility

Existing Hermes and DSH Gate semantics remain unchanged: OFF / Shadow, independent Gate enablement, fail-open observational path and reversible integration. The new classifier/benchmark is isolated and cannot execute tools or retries. Scripts do not read private native traces or export credentials.

**Recorded regression (2026-10-20): Python 996/996 PASS** (including 45 new Phase 8.3 tests, the updated frozen Phase 8.2A allowlist, and existing Hermes/DSH regression), **DSH Vitest 64/64 PASS**, **TypeScript typecheck PASS**, **DSH build PASS**. Public release builder/sanitizer and final clean-source verification are separate mandatory release checks; failing or missing evidence must remain BLOCKED. Missing automated Codex Review does not constitute approval.

The methodology references JevAny solely as published research context. No JevAny code, training scripts, data, prompts, model weights, visual assets or package dependencies were copied or used.

## 7. Acceptance matrix

| Dimension | Phase 8.3 finding |
|---|---|
| Engineering Acceptance | **PASS, offline scope only** subject to the recorded final clean-check tests |
| Decision Opportunity Contract | **PASS, synthetic/metadata contract scope** |
| Native Real Provider Validation | **BLOCKED**, new paid budget not authorized |
| Independent Benchmark Quality | **LIMITED**, historical public data and no new independently adjudicated native tasks |
| Laya Incremental Value | **NOT_ESTABLISHED** for real Agent work; **mixed** on existing public cases |
| Actual Agent-level Savings | **NOT_MEASURED** |
| Active Readiness | **NOT_AUTHORIZED** |

## 8. Recommendation and next criterion

Prioritize a **new independent evidence set**: sample mixed native tasks with independently checked ground truth, sample Completion states where rules already settle the decision, and investigate genuinely ambiguous low-risk Retry recovery points. Use appropriate abstention and acceptable-choice sets, not artificially single-label tasks.

Only after new post-8.2B real StepFun + Laya Shadow E2E under a strict physical-request budget and independent native oracle, consider a separately approved non-mutating Canary for low-risk decisions. Do **not** accelerate to 8D Action Risk Gate or Active solely on these retrospective accuracy rates.

**Implementation status:** source and full Python/DSH regression validated on the isolated feature branch. The GitHub PR and commit metadata must match the actually published branch state, not hypothetical identifiers.

## 9. GitHub PR and review status (2026-10-20)

- Feature: `feat/phase8-3-decision-value` from verified GitHub `main` at `062d52e753e7e00d91a536dc81e9d85b8819cb12`.
- Main engineering commit: `20352d7afb1cd83258eed7918fe97d0e3c5e61ea`.
- **Draft PR [#9](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/9): OPEN / DRAFT / NOT MERGED.**
- Independent code review remains pending. Codex automated review was turned off by the maintainer; lack of a new review notification is not evidence of approval.
- Explicitly out of scope: updating NAS `main`, changing production Hermes/DSH profiles, authorizing real paid StepFun runs, Active decisions, automatic merge, or deployment.


## 10. New preregistered synthetic holdout supplement (2026-10-20)

**This section postdates the original 210-case public historical replay and
does not silently replace it.** The new 80-case cohort is separately frozen
in Git at `1245a3cb17120f0f6bee198a34aa159ea3eeb851` **before** Laya
was invoked. See [prereg protocol](PHASE8_3_NEW_HOLDOUT_PROTOCOL.md) and
[detailed findings](PHASE8_3_NEW_HOLDOUT_REPORT.md).

- Completion: 40 simulated cases, B0 Rule-only **30/40 (75%)** vs rules-matched
  C0 Laya **30/40 (75%)**, 15 real MLX calls, 14 threshold safety overrides.
- Retry: 40 separate policy-controlled fault-injection cases, B0 Rule-only
  **36/40 (90%)** vs C0 Laya **40/40 (100%)**, 14 real MLX calls and zero
  policy-forbidden retry recommendations on the 33 blocked cases.
- Captured local model invocations **29/29 completed**. Real StepFun native
  requests **0**, Native Agent outcome **NOT_MEASURED**.
- Gold is newly authored synthetic/fault-simulation editorial truth, **not
  an external adjudicated real Agent oracle**. The 100% Retry result is
  limited by handcrafted selection and 40-case support. Posthoc
  positive-flag Completion shortcut perfection indicates fixture bias,
  not an Active policy approval.

**Latest supplemented regression:** Python **1008/1008 PASS**,
DSH Vitest **64/64 PASS**, TypeScript typecheck and build PASS.
Publication sanitizer and post-commit cleanliness are separate gates.

**Engineering / freeze checks: PASS (offline); real-world incremental
value NOT_ESTABLISHED; production Active NOT_AUTHORIZED.** The original
Phase 8.3A real Provider requalification remains BLOCKED pending an
explicit budget and independent native test oracle.


## 11. Phase 8.3A attempted real-provider requalification (2026-10-21)

After the separately authorized bounded 8-case StepFun Step Plan + Laya
Shadow protocol was frozen in Git, tool safety checks blocked the
creation of a newly authenticated isolated native test environment.
We did **not** bypass the block, copy credentials or touch production.

The actual 8-case real-provider experiment **has not run**. The
independent native-verification result, exact post-change real
native-to-HTTP causal linkage, physical request budget use and live
Agent task outcomes all remain unmeasured / BLOCKED. Existing 8.2A
real StepFun and 8.2B native Mock records cannot fill that gap.

See [native real test protocol](PHASE8_3_NATIVE_REAL_SHADOW_PROTOCOL.md)
and [attempt and blocker report](PHASE8_3_NATIVE_REAL_ATTEMPT_REPORT.md).
Offline budget/evidence tests can pass without promoting this status
to a real-provider acceptance. Latest scoped regression Python
**1012/1012 PASS**, DSH Vitest **64/64 PASS**, TypeScript
typecheck/build PASS. PR #9 remains Draft; Active remains
NOT_AUTHORIZED.
