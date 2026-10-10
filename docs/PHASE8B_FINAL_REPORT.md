# Local System One Phase 8B — Completion Calibration & Real-World Validation

**Date:** 2026-10-10 · **Scope:** Shadow-only · **Status:** completed technical pilot, real-world acceptance outstanding

**Judgments (separate):**
- **Engineering Acceptance: BLOCKED** for the full Phase 8B contract. Experimental adapters/tests pass, but independent native Hermes **and** DSH provider-backed Agent E2E and real adjudicated corpus are not yet available. This must not be mislabeled as a completed full Phase 8B.
- **Model Quality: NO-GO** for safe control or a demonstrated product-level advantage over rules.
- **Active Readiness: NO-GO**. No automatic task termination, skipping checks or rerouting is authorized.

The core finding is **not** that the model is useless. It is that Laya can often classify easy completion cases better than rigid rules, **yet** it mistakes substantively unfinished tasks for Complete under adversarial phrasing, and a safe evidence-gated hybrid has not beaten rule-only on the frozen synthetic pilot.

## 1. Phase 8A baseline reproduced

See [PHASE8B_BASELINE_AUDIT.md](PHASE8B_BASELINE_AUDIT.md) for hashes and immutable details. NAS baseline SHA `afa2512cc66400d111c28cb5fe00e9f83fdba49a`, public GitHub main observed SHA `920caef1615ae08d76825b5b81ec32af5fc1e7ec` (different sanitization history). Original 120 cases: 30 public-result reconstructions, 90 synthetic. Each split accuracy **63.33%**, macro F1 **0.5308**, Complete recall **0%**, Continue recall **90%**, Verify recall **100%**, zero premature Complete. Original 8A algorithm and threshold were left unchanged before replay.

## 2. Raw model and safety threshold

56/120 decisions came from deterministic rules, 64/120 actually reached Laya. Raw outputs from those 64: Complete 40, Verify 17, Continue 7. **All 40** labeled Complete were raw Complete, but were downgraded by `P(complete) < 0.70`. Raw Complete probabilities **0.417–0.6184**; mean **0.575235**. Raw model-only old-set accuracy **60/64 = 93.75%**, but old-set raw hybrid has no independent safety value. Reported response `confidence` differs from the top-class probability and must not be conflated with calibrated posterior. Original checkpoint configuration temperature is `[1,1,1]`; the cause of sub-0.70 Complete scores has not been shown to be a temperature clamp or a bug. Context, criteria overlap, prompt representation and training distribution remain possible sources of uncertainty.

## 3. New datasets, provenance and isolation

A 45-case synthetic pilot calibration split and a 45-case **separately frozen synthetic holdout** split have 15 different task families each, with 15 Complete, 15 Continue, 15 Verify labels. Freeze SHA256:
- Calibration `b91bbbfdcdc3be1000574456682647148ce7fc46f1a864fb49c9aec84cdf4dd5`.
- Holdout `9074d797a7f56f9506d28199bd5680b9edc6a3108f225d3e976ba52a3921e369`.

An additional 45-case synthetic **adversarial stress set**, 15 per class and all `execution_state={}`, challenges deceptive partial-completion language. Freeze SHA256 `fa7324fcee611988c9ed3f92d6a0ac1f7af81b9b22c2fcb219f86dbc22856b2b`. This stress set was evaluated after the pilot holdout and is **not** a substitute for untouched production blind labels. All sample families are synthetic and public-safe; this stage did **not** gather and adjudicate a new genuine Hermes/DSH production corpus. A stopped Agent is not presumed Complete. User-requested private original history and credentials are not published. Existing private Hermes sessions did not furnish an adjudicated corpus in this run.

## 4. Calibration policies

See [PHASE8B_EVALUATION_PROTOCOL.md](PHASE8B_EVALUATION_PROTOCOL.md). **A:** original 8A threshold 0.70 + hard rules. **B:** conservative rule-only with explicit final-verified and checks-complete flags; otherwise Verify unless hard Continue. **Raw (offline only):** hard rules plus unguarded model choice, no stop authority. **Candidate:** hard rules plus raw Complete only when `P>=0.50` *and* both explicit completion evidence flags are true; else Continue or Verify. The 0.50 value and evidence rule were committed **before the first holdout inference**, commit `da35a367ac09621b3bc441c655b8371be004a033`. This policy is offline-only; **Runtime threshold and live adapters were not changed**.

## 5. Frozen synthetic pilot holdout results (45)

| Policy | Accuracy | Macro F1 | Complete precision / recall | Continue P/R | Verify P/R | Premature Complete |
|---|---:|---:|---:|---:|---:|---:|
| 8A | 55.56% | 0.4667 | 0 / 0% | 1 / 66.7% | .4286 / 100% | 0/30 |
| Rule only | 66.67% | 0.6556 | 1 / 33.3% | 1 / 66.7% | .50 / 100% | 0/30 |
| Raw choice (unsafe offline) | **82.22%** | **0.8261** | 1 / **80%** | 1 / 66.7% | .6522 / 100% | 0/30 |
| Evidence hybrid | 66.67% | 0.6556 | 1 / 33.3% | 1 / 66.7% | .50 / 100% | 0/30 |

Truth-row order Complete/Continue/Verify, predicted columns Complete/Continue/Verify:
- Original: `[[0,0,15],[0,10,5],[0,0,15]]`.
- Rule-only and candidate: `[[5,0,10],[0,10,5],[0,0,15]]`.
- Raw: `[[12,0,3],[0,10,5],[0,0,15]]`.

These are synthetic holdout findings only. The source scripts are publishable, but these 45 rows **must not be reused as a new blind test after publication**.

## 6. Evidence of Laya incremental value (and its limit)

Raw plus rules improves synthetic holdout accuracy by 15.56 percentage points over simple rules, but evidence-constrained candidate **does not** improve either accuracy or macro F1 over rules. The model therefore adds classification information but has **not** demonstrated a safe, positive *net* product benefit. The paired Agent-level Baseline A (native) / B (rules) / C (Laya) comparisons of task success rate, tool counts, repeated calls, LLM tokens and duration remain **NOT MEASURED**: Shadow observations intentionally do not change native execution, so claiming saved LLM tokens or tool calls would be fabricated.

## 7. Adversarial safety results (45)

Text-only stress set deliberately omits verified structured evidence. Raw-choice accuracy **57.78%** and macro F1 **0.4638**; **five of thirty non-Complete cases were classified Complete** (5/30=16.67%, 95% Wilson interval **7.34–33.56%**). All five were explicitly unfinished Continue cases, such as staging mistaken for production, approved-not-merged PR, unfinished translation, local commit not pushed, and dry-run mistaken for rollout. Raw Complete precision **11/16=68.75%**, Complete recall **11/15=73.33%**. Existing 8A, rule-only and evidence-hybrid all produced zero premature Complete **because all 45 cases defaulted to Verify**; their accuracy is only **33.33%**, Complete recall **0%**, and none is evidence of a useful completion controller.

The original 45-case holdout had 0/30 dangerous events: Wilson 95% upper **11.35%**. Zero in a small set is not evidence for safe Active. The adverse rate is purposefully enriched and must **not** be presented as a population/base-rate estimate; it is a falsification of the unsafe raw-choice policy.

## 8. ANE/MLX quality and cost

Legacy 8A model cases: **64/64 raw decision agreement**, **120/120 final agreement**, mean absolute `P(complete)` backend difference 0.000667, max 0.0020. Frozen synthetic holdout: **25/25 raw**, **45/45 final** agree, mean difference 0.000572, max 0.0021. Strict bitwise/shape equivalence is not established. Both use nominally the same 421M checkpoint and typed criteria but different execution paths and numerical precision.

| Model-only HTTP wall timing | ANE P50 | ANE P95 | MLX P50 | MLX P95 |
|---|---:|---:|---:|---:|
| Legacy 8A n=64 | 54.55ms | 57.31ms | 49.52ms | 62.30ms |
| Frozen holdout n=25 | 54.59ms | 63.89ms | 49.43ms | 51.70ms |

Numbers include local loopback, serialization and cold/warm variability, **not** ANE-only kernel time or energy. A separate isolated MLX-only Runtime process was observed at approximately **944,672 KiB RSS** during a smoke run; no comparable isolated ANE memory or measured power data were obtained. Thus **ANE high-frequency energy advantage is NOT PROVEN**, and ANE does not reliably beat MLX in these small wall-time samples.

## 9. Hermes Agent Loop probe

Installed Hermes identified as `0.21.6+153.g51609d8.dirty`. Actual native `post_tool_call` dispatcher and its per-tool identity were inspected in the installed Hermes source; it is an observational bounded hook. An **independent default-OFF** `completion_loop_probe_enabled` toggle was added to the existing adapter; it probes at most **once per turn after the first observed tool result**. Existing `on_session_end` observer stays intact. Requests carry task and a generic progress sentence, *not raw tool output*. Only metadata is stored. The native hook callback returns `None`, never mutates tools, model, or termination. Errors/invalid Runtime responses fail open. Hermes manifest validation and doctor passed, and synthetic hook replay reached a separately launched actual MLX Runtime on loopback port 8788 for both mid-turn and end-turn calls.

**Important limit:** The first tool completion generally does **not** establish whole-task satisfaction. This proves lifecycle/transport feasibility, not useful Active evidence. Hermes synchronous adapter call adds decision latency on that tool-result hook (roughly a model inference wall-time; worst case bounded by existing timeout settings). Future asynchronous/batched model observations should be tested before allowing frequent probes.

## 10. DeepSeek Harness Agent Loop probe

Pinned upstream lifecycle inspected at commit `477b4f420553e8a52c2fbccc464d7561b239c443` (DSH `0.1.7-rc.2`), not assumed interchangeable with all newer prereleases. Adapter `0.5.0` now supports a separate default-OFF `completion_loop_probe_enabled` option. The native `session/event:tool/result` observer captures **one per session:turn**, and submits its probe asynchronously, so it does not await the Completion call. `turn/end` still submits a separate observation and the session/turn maps are cleared. In-repo lifecycle tests and a real HTTP test against the separate MLX Runtime passed for both stages. A production DSH installation/provid­er-backed **native Agent task** was not exercised; version breadth is **NOT** proven. No core DSH code was modified.

## 11. Agent cost and possible scheduling policy

The isolated synthetic holdout required 25 Laya calls for 45 cases; the other 20 were handled by hard rules. Mean model question length was **164.28 tokens** (range 156–181) in that replay. Those are **local model input tokens**, not an LLM API bill. Completion adds no provider prompt tokens by itself. With the opt-in loop probe, an ordinary turn with tools can produce **up to two Completion calls** (one after the first tool and one at turn/end); zero-tool turns can still be evaluated at turn/end. A rough 50–65 ms per inference can become ~100–130 ms of aggregate extra local work on a 2-call turn before scheduling/network variance. This is **not** a measurement of end-to-end Agent delay. Only a state-change/completion-candidate event-driven strategy could justify frequent calls; the first-tool one-shot is a feasibility probe, not an optimized scheduler.

## 12. Risk and fail-open

Completion is still a semantic recommendation, not a control command. No setting enables automatic stop, skips verification or denies tools. Existing Search/ModelTier/Notification Gates, Contract v1 and OFF/Shadow/Canary remain. Probe is independent and defaults false in both adapters; disabling it restores the earlier turn-end behavior. Transient raw task only stays in bounded process memory; tool results are not put into the new probe request/log. Failure cannot interrupt native Agent execution. Real live shutdown/degraded-native tests and a long concurrency stress soak remain incomplete, so absolute noninterference is not established.

## 13. Tests and technical acceptance

- Repository Python full regression: **114/114 PASS**.
- DSH Vitest: **43/43 PASS**; TypeScript `tsc --noEmit` PASS; production `tsc` build PASS.
- Hermes `plugins validate` PASS, `plugins doctor --ci` PASS on installed Hermes.
- Hermes new probe unit tests: one per turn, default off, telemetry privacy, error fail-open.
- DSH new probe tests: one per turn, default off, unchanged native event dispatch, error fail-open and gate independence.
- Independently hosted Runtime `127.0.0.1:8788` MLX-only: real HTTP integration PASS for both adapters, mid-loop and end-turn.
- ANE/MLX agreement on both legacy and pilot samples as described.
- The new public release sanitizer must PASS before publishing; no credential or original transcript can ship.
- **Not performed:** genuine provider-backed, matched native Hermes and DSH runs measuring successful tasks, tool use and user outcome. Therefore overall Phase 8B engineering acceptance remains **BLOCKED**.

## 14. Code and versions

NAS origin/main starting SHA: `afa2512...`. Policy/corpus frozen before pilot holdout: `da35a367ac09621b3bc441c655b8371be004a033`. Worktree branch: `feat/phase8b-completion-calibration`. Modified Hermes adapter (new config and post_tool observer), DSH adapter (new config and tool-result event observer), tests, and new offline benchmarking scripts/docs. Adapter versions during validation remain Hermes `0.8.0` and DSH `0.5.0`; source changes are not an automatically installed released plugin.

## 15. GitHub publication and Review

Public PR/review status must be filled from actual GitHub records; **do not call this merged or reviewed before confirmation**. Workflow: commit reviewed changes in NAS Git development branch, generate allowlisted/sanitized public tree, publish as an isolated branch based on public/main, open PR, address real Codex Review, merge only after checks and review. No force pushes.

## 16. Known limits and interpretation

All newly curated samples are synthetic and formulaic. Published 8A `real` cases are reconstructed public outcomes, not raw traces. Neither source supports a production base-rate of dangerous premature completion. An ECE of ~0.22 on 25 holdout model-only cases is an unstable diagnostic, not a reliable calibration mapping. Recorded ANE/MLX latency mixes cold/warm/system load, no measured energy benefit. Current mid-turn summaries have little verified tool-state content. Genuine Agent-level cost/savings and architecture-safe Active interception require separate future work.

## 17. Next stage and go/no-go

**Do not start Active Completion or lower the production threshold.** First collect genuine Hermes/DSH task traces (originals only in NAS private storage), independently adjudicate Complete/Continue/Verify from user requirements and external outcomes, and freeze a larger temporal/repository-separated blind corpus. Next, improve evidence extraction for artifacts/tests/remote PR/deployment state without persisting raw text; prove that Laya adds measurable safety-adjusted incremental value over simple rules and the additional runtime latency; benchmark a low-frequency candidate-triggered loop policy against native paired tasks; then revisit Active controls in a separately authorized phase. If advantage remains absent, retire or constrain the model-based Completion path to passive diagnostic assistance.

**Final: Engineering BLOCKED / Model Quality NO-GO / Active Readiness NO-GO.**
