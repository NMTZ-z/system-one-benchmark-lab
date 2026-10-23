# Phase 8.3 — Decision Opportunity & Value Validation

**Checkpoint: 2026-10-20. Status: OFFLINE ENGINEERING ACCEPTANCE (LIMITED). Paid Native StepFun requalification BLOCKED. Active NOT AUTHORIZED.**


**Latest 2026-10-21 addendum:** Three *actual* Hermes + StepFun
Step Plan native read-only tests are now completed: H1 OFF
PASS_SCOPED (one original physical Provider result missing), H2
real Laya/MLX Shadow PASS_SCOPED (2/2 causal links), and H3
Runtime-down Shadow PASS_SCOPED (2/2 HTTP 503, 2/2 failed_open).
There have been 8 real physical Provider attempts, 7 recorded HTTP
200 and 1 original H1 attempt without terminal evidence. The global
budget/Provider-billing gate remains **BLOCKED** and Active is
NOT_AUTHORIZED. Historical startup-era sections below are retained
as dated checkpoints, not as the latest native-run status. See
Section 16 and the [H3 report](PHASE8_3_REAL_NATIVE_H3_REPORT.md).

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


## 12. New credential-free profiles and SDK preflight (2026-10-21)

A new OFF-only Hermes test home and independent DSH OFF/Shadow SDK
configurations have been created without reading or linking any old
credential. The official DSH SDK completed initialization and shutdown
in both modes using an explicitly empty environment, zero Agent tasks,
and zero StepFun main-model requests.

This is offline engineering progress ONLY. A supported fresh Hermes
interactive login and separately secure DSH credential input are still
necessary before real Provider E2E is possible. The tool security block
was not circumvented. Phase 8.3A real Provider validation stays
BLOCKED, exact native-to-HTTP correlation stays NOT VERIFIED on new
real traffic, and Active stays NOT AUTHORIZED.

See the official auth handoff PHASE8_3_OFFICIAL_AUTH_HANDOFF.md and
the amended attempt report PHASE8_3_NATIVE_REAL_ATTEMPT_REPORT.md.
PR #9 remains Draft.


### Credential-free fresh-profile hardening result

Full Phase 8.3 code regression after the new safe isolated-home and DSH
SDK offline bootstrap work: **Python 1030/1030 PASS**, DSH Vitest
**64/64 PASS**, TypeScript typecheck/build PASS. The fresh Hermes
Home contains no credential and the read-only preflight correctly
returns BLOCKED (MISSING_NEW_PROFILE_LOGIN). The two official DSH
OFF/Shadow SDK initialization/shutdown paths both pass without a
credential or any main-model call.

This does not supersede or inflate the 80-case synthetic benchmark,
does not establish native StepFun outcome and does not grant
Active rights. See the official auth handoff.

## 13. Authentication bootstrap recovery without credential reuse

A user attempting the fresh Hermes test Home encountered Hermes PM's
missing committed dependency environment. Inspection proved that the
owner install's committed venv under ~/.hermes/installs was not
available to an external repository-private HERMES_HOME. A bounded
scoped repair was attempted but timed out before installation committed;
the test-only partial state was cleaned up.

A NEW Home under the existing owner data root
(~/.hermes/system-one-phase83lab) was then prepared with public
System One plugin files, OFF-only configuration and an empty .env.
Hermes' official authentication status works there, correctly saying
stepfun: logged out, without touching the owner's configuration,
sharing old secrets or sending any Provider call.

The secure owner-entered login is still needed. Native Provider
acceptance remains BLOCKED, with no billable requests initiated
and no Active authority. See the updated official auth handoff and
attempt report for the exact scope and instructions.


### Final isolated auth/bootstrap regression

The fixed new Hermes Home under ~/.hermes/system-one-phase83lab
inherits only the parent's already committed *dependency environment*.
The new test Home's config and credentials are its own; old auth files
were neither read nor copied. The native runner now accepts ONLY this
one extra pinned Home after independent credentials/URL checks, while
keeping existing hard Provider/task limits.

Latest scoped regression: **Python 1051/1051 PASS**, **DSH
Vitest 64/64 PASS**, TypeScript typecheck and build PASS. No
additional paid Provider calls or real Agent native tests occurred.
The PR remains a draft until native success/failure quality and
cost evidence are independently demonstrated.

## 14. Real StepFun H1 OFF task and Provider-ledger blocker

The first **real** Phase 8.3A Hermes OFF native read-file trial
ran against pinned code 82993477667817c8941caa429feea576d091a424.
Native tool and independent original-file oracles all PASS.
Physical StepFun main Provider traffic was **3 attempted** with
only **2 recorded HTTP 200** and 1 attempted/unfinalized slot.
The 8.2B reconciler returns **BLOCKED** on
reserved_without_proxy_result. This is not a real Laya quality
result and token/fee benefits are NOT MEASURED.

The original test harness ended the provider proxy as soon as
Hermes returned; a new bounded drain prevents premature termination
of future already-reserved outbound lifecycles, but does not
retroactively supply a missing Provider response. There has been
**no rerun and no further paid requests** while accounting is
blocked. H2-H4 and D1-D4 are still NOT RUN. Active remains
NOT AUTHORIZED.

Read the dedicated Phase8.3 real H1 report and its frozen
machine-readable evidence before interpreting the historical
synthetic benchmark as native Agent benefit.

### Phase 8.3A post-real-H1 regression and budget integrity

The one-shot H1 native Agent task genuinely passed its independent file
oracle, but the physical Provider ledger recorded 3 attempted requests,
only 2 acknowledged HTTP 200 responses and 1 missing terminal event.
The independent 8.2B Budget Reconciler explicitly returns BLOCKED.
Future tests now have a bounded provider-transport lifecycle drain,
but **H1 was not rerun** and its missing event was not fabricated.

The amended post-run regression is **Python 1082/1082 PASS**,
**DSH Vitest 64/64 PASS**, TypeScript typecheck/build PASS.
Further paid E2E is stopped pending complete safe reconciliation.
Original main Agent token and billing savings remain NOT_MEASURED,
and Active remains NOT_AUTHORIZED.

## 15. True Hermes H2 Shadow StepFun + Laya E2E (2026-10-21)

An independent one-shot real H2 trial, on predeclared frozen source
0dc626ff86038702f74027b4a988d21f096f72d9, achieved a full
native read-only task and 2 real Laya/MLX Completion Shadow model
decisions. Native tool call/result, private file content and final
Agent answer were independently verified. Exact HMAC causal
correlation between actual native Hermes, Adapter and Runtime
HTTP proved **2/2** links.

The same durable physical Provider ledger retained all original
three H1 requests, including the unfinalized historic one.
H2 added exactly three new real physical requests, each with
HTTP 200 and a completed terminal/result lifecycle. Thus H2
transport lifecycle is **COMPLETE_SCOPED**, while H2 budget
token/charge provenance remains **PARTIAL** (3 physical vs
2 logical main-model calls, one unattributed, all Provider billing
unknown).

Overall Phase 8.3A Provider budget integrity **remains BLOCKED**
because H1 slot 1 has no terminal record. H3/H4 and D1-D4
remain NOT RUN. No native Agent task was stopped, retried or
rerouted by System One Shadow advice, and no realistic billing
or savings effect was measured.

See the detailed real-H2 report PHASE8_3_REAL_NATIVE_H2_REPORT.md,
the public aggregate, and the independently verified original
post-run data. H2 pre-run source is distinct from subsequent
report-only commits and GitHub main remains unchanged.


### Post-H2 independent verification and regression

An independent post-run replay of H2 physical ledger, real native
tool/hidden-file SQLite evidence, original MLX HTTP records and
private HMAC join yielded **H2 PASS_SCOPED**, three StepFun HTTP200
terminal records, zero H2 attempted-unresolved events, two
verified local model invocations, and exactly 2/2
native-to-Runtime causal links. The H1 historical physical request
was never altered.

The H2 usage/billing reconciler returns PARTIAL (one of its three
physical calls is not attributed to two self-reported logical calls;
Provider-reported token charges are unknown). H1 remains BLOCKED.
Post-run Python **1121/1121 PASS**, DSH Vitest **64/64 PASS**,
TypeScript typecheck/build PASS. No further live Provider requests.

## 16. Executed H3 real Runtime-down Shadow and title-generation hypothesis (2026-10-21)

On frozen predeclared H3 real-provider source
40a7b4416db07e6eedcf505131e0c9b3e1a98eac,
Hermes/StepFun completed a **real native read_file** task while the
System One Laya Runtime was intentionally not running. A separate
observer recorded **two actual HTTP 503** responses, both native
Completion observations were marked **failed_open**, and the
independent HMAC/native SQLite/Adapter/HTTP verifier proved **2/2
exact causal request links**. The task's original file bytes, tool
result and Agent answer matched independently; the native Agent
exited normally after 13.632 s. No Active/canary action was enabled.
The isolated Hermes test Home was returned to OFF and all test-only
services stopped.

The original H1/H2 Provider ledger (6 slots) was hash-frozen first.
H3 appended **two actual physical StepFun requests** in slots 7–8;
both reached real HTTP 200 and terminal proxy results. Agent
self-reported two main calls, matching H3's physical attempts.
Only in this NEW test Home, for H3, background LLM title upgrading
was disabled while nonmodel instant titles remained enabled.
Installed Hermes source confirms a concurrent model-backed title
upgrade is enabled by default, and H2's extra long-lived physical
call outlasted the Agent process. **This supports, but does not
prove, the title upgrade attribution of H1/H2's extra call**.
Those earlier physical slots still have no per-request role identity.

Global historical Provider budget remains **BLOCKED** because H1
slot 1 is still attempted/unfinalized. Total physical attempts
now **8/24**, seven recorded HTTP 200, one H1 unknown. The
remaining nominal 16 slots are NOT permission for more Provider
tests. H4 and all DSH real tasks are NOT RUN. Token and subscription
cost changes have NOT BEEN MEASURED; Active NOT_AUTHORIZED.

An independent read-only post-run H3 verifier checks the frozen
original file/native SQLite/HTTP/HMAC and cumulative ledger.
H2 historical re-verification was fixed to select H2's own two
keyed request refs, allowing later H3 events to be appended
without altering H2's original acceptance. See the separate
[H3 real report](PHASE8_3_REAL_NATIVE_H3_REPORT.md),
[H3 preregistration](PHASE8_3_REAL_H3_PREREGISTRATION.md) and
privacy-safe H3 machine-readable aggregate.

## 17. H4 failing-native-tool oracle and DSH credential isolation (2026-10-22)

This update is OFFLINE engineering qualification only. No extra
StepFun main Provider call was made beyond the eight physical
attempts already recorded in H1/H2/H3 (7 terminal HTTP 200,
1 original H1 unknown).

The H4-only native runner scenario has been limited to
read_missing with Hermes, Shadow, the exact h4_missing_read case ID
and original 24/3 physical request budget. A pre-Agent private
target manifest records a new randomized ABSENT disposable file;
the native tool must make one read_file call and return true
structured not_found/error bytes paired to the tool-call ID.
Agent final prose by itself is never a negative tool-result oracle.
Pure synthetic independent SQLite tests reject altered targets,
fake successes, duplicates, unrelated tools, missing IDs and
unexpected side effects.

Critically, a zero-Provider direct call to the actually installed
Hermes read_file and its typed result observer was executed:
the file stayed absent, the returned JSON carried not_found=true,
and Hermes' observer classifier derived status=error,
error_type=tool_error. This establishes a necessary typed failure
signal for a subsequent Retry Shadow test, but the full Agent
post_tool_call event and actual Retry advisory remain NOT VERIFIED
until a real one-shot H4 native task. No active retry was enabled.

The cumulative ledger reader now reserves slots 9 onward for
H4 and checks SHA-256 of the entire original 30-row H1+H2+H3
prefix. Its three historical case results remain independently
reproducible and the H1 missing terminal is not backfilled or
refunded. No budget reset occurred.

For DeepSeek Harness, the existing pinned native SDK OFF/Shadow
bootstrap has again passed without model calls or credentials.
A new separate read-only admission checker verifies the exact
pinned upstream commit, StepFun single-model loopback patch,
zero SDK retry, non-Active Gate, securely scoped private HOME
and unchanged 8-physical-request global ledger. The DSH native
session.event validator requires one paired read tool call/result,
matched Session/Turn identity and correctly typed isError for
D1–D4; synthetic tampering is rejected. This DOES NOT prove
real DSH model execution, original bytes, keyed HTTP correlation
or any paid Provider usage.

DSH real E2E is still BLOCKED_PENDING_OWNER_SECURE_INPUT:
the DSH SDK references STEPFUN_API_KEY only by name, not by
an embedded token. A future separately authorized, one-shot
DSH native runner will require an owner-entered process-scoped key,
hard budget/route attestation and a real independent tool oracle.
No old Hermes test Home or production credential was read or copied.

Read the distinct [H4/DSH offline qualification and acceptance
criteria](PHASE8_3_H4_DSH_OFFLINE_QUALIFICATION.md). PR #9 remains
Draft; overall historical Phase 8.3A real-provider integrity
BLOCKED, fee/token savings NOT MEASURED, Active NOT_AUTHORIZED.

### Phase 8.3A post-H4/DSH offline regression (2026-10-22)

The no-Provider H4 negative tool/read-failure and DSH SDK native
evidence design passed full regression **Python 1201/1201 PASS**,
**DSH 64/64 PASS**, TS typecheck/build PASS. The H4-only read_missing
scenario and original private manifest are guarded by strict
platform/ID/mode and an independently absent file oracle; Hermes
native tool error and typed observer classification were exercised
without a model call. DSH native SDK OFF/Shadow init remained
credential-empty and its model/provider patch restricted to localhost
18794 and zero provider-owned retries. Actual H4/DSH native StepFun
execution is **NOT RUN** and remains separate from this evidence.

The original 8/24 cumulative Provider attempt budget is unchanged;
historical H1 slot 1 remains unresolved and actual StepFun credits
cannot be independently measured. PR #9 remains Draft; Active remains
NOT_AUTHORIZED. See the dedicated H4/DSH offline qualification report.

## 18. H4 Gateway-native admission block (2026-10-22)

After 1231 pre-run Python tests, 64 DSH Vitest tests and a clean
289-file public sanitizer, one H4 frozen failed-read attempt
(sha a32eb078593cb4a9139c9aa181d017b9bb010298) was started.
The test Home remained the previously isolated Shadow-only
Hermes Home, main Provider solely StepFun Plan behind the
24-global/3-case proxy. However the latest Hermes CLI one-shot
first required the host Gateway. That production-owned multiplexing
Gateway was already serving default and other existing Profiles,
while the nonregistered H4 test Home was not served. The native CLI
therefore refused startup BEFORE a native Agent Session, file-tool
call, Completion/Retry Shadow observation or physical StepFun
main-model request.

The isolated H4 original missing-file target was never created.
No H4 Provider slots were reserved or attempted. The original
cumulative Provider ledger digest remains
5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb:
**8/24 physical attempts, 7 HTTP 200, original H1 1 unknown**.
The test Home was returned to OFF and test-only services stopped;
the production Gateway was NOT restarted, stopped, modified or
forced to serve the test Home.

The original frozen child Hermes process exited with code 1, but
the native Python wrapper returned shell status 0, a false-success
risk despite the outer H4 verifier correctly marking the overall
result PARTIAL_OR_BLOCKED. Later code changed the wrapper to
propagate a nonzero exit for any underlying Agent failure, timeout
or unknown status. That correction does NOT retroactively change
the H4 result. An independent read-only source+private evidence
verifier confirms the Gateway refusal, no native Session and no
Provider attempts, with only privacy-safe aggregate output.

The installed official Hermes source still provides an in-process
run_oneshot entry which directly creates AIAgent without connecting
to the Gateway. This potential future alternative was verified by
import/source inspection only and made no Provider calls. It is
NOT a tested real Agent execution and H4 will not be automatically
re-run. A future H4B requires a distinct preregistered case,
clean SHA, original cumulative ledger and separate authorization.

See [H4 Gateway admission incident](PHASE8_3_H4_GATEWAY_ADMISSION_INCIDENT.md).
H4 Retry/Completion real-native E2E remains NOT RUN; H2/H3
prior scoped PASS are preserved, DSH native D1–D4 remain NOT RUN
pending owner-controlled independent credentials. Active remains
NOT_AUTHORIZED; PR #9 stays Draft and unmerged.

## 19. Reversible H4B in-process native Agent source preregistered (2026-10-23)

With the user's explicit concern about permanent local effects,
H4B is a distinctly named new native experiment rather than
retrying/overwriting the old H4 Gateway-block evidence. Its
preregistered source uses the installed official in-process
Hermes run_oneshot/AIAgent (not the Gateway-backed CLI -z)
behind a macOS Seatbelt process sandbox. The OS denies
writes outside preapproved test SQLite/locks, test plugin
state and a new disposable H4B folder, and denies network
outside the localhost 18793/18794 observer/physical cap.
The child exposes only native read_file with an exact
preregistered absent-file path; no shell, browser, network
tool or native auto retry is authorized.

Before any H4B Agent process, a separate 0700 Git-ignored
recovery directory captures SQLite online backup, test
plugin state/lock, test config and public plugin source,
with SHA checks. Original credential contents are not
copied/exported, and the original test Home is restored
to its exact OFF logical state when all verified owned
process groups have stopped. Interrupted runs have a
stat/UID/PID/PGID/start-time process ledger and explicit
owner-controlled manual stop/rollback path. An identity
mismatch refuses cleanup rather than risking the user's
production Gateway. Private postrun evidence is retained
separately for a later independent audit.

A disposable actual macOS Seatbelt test blocked fake
production SSH/Docs/repo reads and disallowed writes;
a stricter-than-real offline Python import of official
Hermes run_oneshot+single-read toolset PASSED with
ALL network denied and the isolated test Home original
SQLite, config, plugin state and auth metadata unchanged.
Synthetic WAL database rollback, plugin temp-file cleanup,
owned-process PID-reuse rejection, typed native H4B missing
file failure and strict Retry/Completion HMAC correlation
were regression tested. No StepFun requests were initiated
by those preparation actions.

A real H4B one-shot is contingent on full clean-source
regressions and preflight, then separately read-only
adjudication of the true Agent/Retry/Provider/rollback
evidence. Original 8/24 physically reserved StepFun calls
and the unknown H1 historical slot are unchanged;
remaining 16 cannot be interpreted as automatic
authorization. No Active/Canary authority granted.
See the [H4B reversible preregistration protocol](PHASE8_3_REAL_H4B_REVERSIBLE_PREREGISTRATION.md).

## 20. Original H4B Seatbelt safe-denial and complete rollback (2026-10-23)

Frozen, preregistered real H4B source
633c914fe9b78b7515cfcfbe4795f5d2dbd3aadf
started its own isolated MLX, keyed HTTP Observer and
physical-budget proxy after a durable test-Home SQLite/plugin/
config recovery snapshot. The official Hermes in-process
run_oneshot was entered under macOS Seatbelt, but failed
BEFORE AIAgent construction when it attempted to open
/dev/null to suppress stdout/stderr, which the prior default
deny write policy had not permitted.

**Actual H4B native Session/tool and Provider calls: ZERO.**
This is NOT a failed-read native/Retry result. The original
absent-file target remained absent; no true Completion or Retry
HTTP evidence was generated. The original cumulative StepFun
physical ledger is unchanged at 8/24, seven HTTP 200, one H1
historical UNKNOWN.

The original orchestrator did not rerun. It terminated its
own 4 registered process groups, attested PID/UID/PGID/start
identity, archived postrun private SQLite/plugin state and
restored the original isolated test Home SQLite logical digest,
plugin state/source, config and OFF mode. The isolated auth.json
metadata did not change; the test-only network listeners stopped,
production Hermes Gateway/other profiles, NAS and GitHub main
were not modified.

An independent private-evidence-to-public verifier checked
the original frozen H4B exit 1, /dev/null permission failure,
zero H4B Session, unchanged original file, 4/4 stopped process
groups, real Provider tally and successful durable rollback.
The public aggregate deliberately states
BLOCKED_BEFORE_NATIVE_AGENT_CONSTRUCTION.

After the original run, a NEW code revision granted only
macOS /dev/null write access, not arbitrary disk/network
privileges, and strengthened the offline rehearsal to CALL
the official run_oneshot preamble with an in-memory synthetic
Agent stub (no real Agent/Provider or key access). That
strict zero-network rehearsal PASSED while the original
test Home SQLite/plugin/config/auth metadata remained unchanged.
This later fix does NOT retrospectively qualify H4B;
future H4C would require separate original source/case
preregistration and explicit admission.

See [H4B true Seatbelt admission incident](PHASE8_3_H4B_SEATBELT_ADMISSION_INCIDENT.md).
The overall Phase8.3A budget/billing caveat, lack of Active
authority and Draft PR status are unchanged.

## 21. New H4C source isolation and acceptance preregistration (2026-10-23)

The Phase 8.3A H4C distinct real failed-read task was
prepared independently of original H4 (Gateway blocked) and
H4B (Seatbelt /dev/null blocked), with exact new H4C case ID,
manifest, native SQLite evidence, HMAC/Observer output,
PID provenance ledger, online SQLite recovery and private
test files. H4B's original test Home recovery receipts and
historical raw evidence are not overwritten or reused.

Previously proven macOS Seatbelt and official Hermes in-process
one-shot source are reused, with nonpublic file read/write
denials, only read_file to the exact case-owned ABSENT target,
localhost 18793/18794 egress and owner-specific rollback.
Ancillary MLX/Observer/Provider services now use H4C-owned
disposable HOME and caches rather than the user's normal
home. The original H4B incident and all four stopped processes
are independently rechecked before H4C admission.

Global physical StepFun remains at 8/24 from H1/H2/H3,
with H1's single historical outcome UNKNOWN; old H4/H4B
each made 0 paid Provider attempts. New H4C is bounded to
three physical slots 9–11, no reset, no Active/canary or
paid retries. A zero-network case-specific offline Hermes
one-shot rehearsal PASSED. This phase document reflects
source preregistration, not an observed real H4C native result.
Read [H4C preregistration and manual recovery](PHASE8_3_REAL_H4C_PREREGISTRATION.md).

## 22. H4C real native startup blocked before persistent Session (2026-10-23)

The H4C NEW independent case on clean frozen SHA
8776de71a88821dffd84bfd4976927fd0cfe9c3a
passed 1338/1338 prereg Python regression, DSH 64/64,
TS typecheck/build, and a 321-file publish-ready sanitizer.
It passed the strict local-only OFF gate, exact original
H4B recovery verification, fresh H4C rollback scope and
official Hermes one-shot preamble under all-network-denied
Seatbelt with a synthetic no-model stub.

Exactly ONE genuine new H4C official in-process Hermes
one-shot was then started with dedicated isolated Laya,
HMAC Observer and physical StepFun capped local services.
The child returned 1 before any native SQLite Session or
read_file tool. The official usage evidence records
failed=true and failure SystemExit(1); the underlying
source cannot be established because official one-shot
suppressed stderr during _run_agent. No Completion/Retry
HTTP events and NO H4C StepFun physical requests occurred.

The original test Home OFF/SQLite/plugin/config/source
was restored using the new h4c_recovery. Auth stat-only
metadata unchanged; all four H4C-owned process groups
verified NOT_RUNNING. Original H4B separate backup and
H1-H3 private evidence were unaffected. Cumulative
StepFun physical ledger SHA was unchanged at 8/24:
seven recorded HTTP 200, original H1 one UNKNOWN.
No new Provider charge was observed through the proxy,
no production Gateway, NAS main, GitHub main or user
profile was modified. H4C was NOT retried.

An independent post-run H4C verifier and privacy-safe
machine-readable incident were created; real H4C failure
tool and Retry E2E remain NOT RUN. The next work should
instrument the entire real Hermes _run_agent initialization
under a separate zero-network simulated local Provider
and disposable rollback scope BEFORE contemplating a
new paid experiment. Do not weaken Seatbelt on speculation.

Read the [H4C blocked native startup incident](PHASE8_3_H4C_NATIVE_BOOT_INCIDENT.md).
Draft PR #9 remains unmerged, Active/Canary NOT AUTHORIZED,
global Phase8.3A Provider integrity historical BLOCKED.
