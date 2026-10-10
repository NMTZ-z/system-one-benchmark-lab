# Phase 8B evaluation protocol (frozen before pilot holdout inference)

## Acceptance hierarchy

1. **Historical baseline** (`gold_v0.1.jsonl`, 30 public-outcome reconstructions + 90 synthetic): diagnostic replay only, never an independent acceptance split.
2. **Phase 8B synthetic pilot calibration**: 45 labeled examples from 15 new task families (15 per label). May inform thresholds and rules, but cannot establish product readiness.
3. **Phase 8B synthetic pilot blind holdout**: 45 labeled examples from 15 distinct task families (15 per label), frozen **before** any pilot model inference or policy selection. Evaluate precisely once after the policies are locked; do not retune using this split. It still does not substitute for real Hermes/DSH agent history.
4. **Independent real-world Agent corpus**: must collect, human adjudicate and freeze later from separate genuine Hermes/DSH task outcomes. An Agent turn ending is NOT evidence of completion. Until this exists and paired native Agent runs are available, model quality and Active readiness remain **NO-GO** regardless of pilot numbers.

The local data is ignored under `private/phase8b/`. The synthetic source generator is allowlisted and contains no private transcripts. Frozen SHA256:
- calibration 45: `b91bbbfdcdc3be1000574456682647148ce7fc46f1a864fb49c9aec84cdf4dd5`
- blind 45: `9074d797a7f56f9506d28199bd5680b9edc6a3108f225d3e976ba52a3921e369`

## Offline policies locked **before the first blind inference**

- **8A:** existing hard rules followed by Laya choice, raw Complete below 0.70 downgraded to Verify.
- **Rule-only B:** identical hard rules; if explicit `required_checks_completed=true` AND `final_state_verified=true`, return Complete; otherwise abstain to Verify. This is a conservative rule baseline, **not** a new runtime behavior.
- **Raw B (safety-unsafe counterfactual):** original hard rules then raw Laya choice without threshold. Offline analysis only, never Active.
- **Calibrated C:** identical hard rules; only return Complete when raw Laya choice is Complete, its probability is >=0.50, and both explicit evidence flags are true. Otherwise, preserve raw Continue or conservative Verify. Calibration value 0.50 was chosen before inspecting the blind set and is **not** authorized for production/Active.

Compare Accuracy, Macro-F1, full confusion matrix, Complete Precision/Recall, Verify/Continue Precision/Recall and premature completion risk with a Wilson CI (plus exact one-sided upper bound when zero). Rules vs Laya must include incremental inference latency; classifications alone cannot establish net benefit.

## Real-world research, not yet a passed test

Pair identical task goals and explicit acceptance criteria across platforms. Gather task state before stop claims, test results, artifacts, deployment evidence, external PR state and status of skipped checks. Protect private originals on NAS, publish only IDs/hashes/aggregates and independently sanitized samples. Have at least two reviewers adjudicate disputed examples; group split by task or repository family and time, not just rows. Treat the final user deliverable itself separately from tool success, test success, or an Agent's own assertion.

For true Agent-level A/B/C, Shadow-only policies cannot influence actual task execution, so their observed tool counts and success rates should be *identical by design* when paired on the same native run. Token savings and premature termination reduction can only be **modeled** until a later separately approved Active experiment.

All pilot outcomes are for method validation only. Engineering implementation can PASS without authorizing an Active gate.
