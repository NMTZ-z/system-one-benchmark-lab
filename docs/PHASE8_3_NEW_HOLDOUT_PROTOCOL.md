# Phase 8.3 — Preregistered New Held-out Decision Pilot v1

Pre-model registration date: 2026-10-20. This protocol and the dataset,
labels, generator and runner are committed before any real local-model
inference. No label editing, prompt tuning, policy threshold changes, model
selection based on this holdout, or in-place rewriting after seeing results.

## Question and permitted interpretation

Does actual local Laya Typed Decisions 421M inference improve the correctness of
advisory bounded choices over exactly the same hard-rule policy with conservative
fallback? This is a new synthetic/fault-injection study, NOT an independently
verified real-world Agent task outcome study. Gold was written before model
outputs were observed, but the study author also built the evaluation code.
This is not third-party independent adjudication or proof of training novelty.

## Preregistered cohorts

Exactly 80 newly authored public fabricated cases:
- 40 Completion situations, 40 named families, spanning completed, incomplete,
  uncertain and multiple-acceptable-decision situations.
- 40 Retry / Escalation injected failure circumstances, 40 named families,
  covering safe retries, alternate recovery, permission/budget failures,
  timeout/writes with unknown side effects, model escalation suggestions and
  terminal recovery decisions. This is only *advice*, never a tool operation.
- Source labels: synthetic and fault_injection, never native real_agent.
- All samples have manually fixed acceptable sets, preferred recommendation,
  and a textual simulated-oracle rationale before inference.
- Reject exact duplicate canonical model inputs, including a collision with
  historical public Phase 8A Completion and 8C Retry samples. Similar patterns
  can remain, so neither random sampling nor statistical independence is claimed.

## Paired policy arms

A — Native Agent: not observed. Never infer this from an Agent final answer.

B0 — Rule-only: existing production hard rules, then the conservative
Completion default verify or existing Retry deterministic fallback.

C0 — Rules + Laya: the EXACT same hard rules and bounded candidate policies.
Invoke local MLX ONLY on unresolved cases. Keep current Completion complete
confidence threshold 0.70 and all Retry safety checks unchanged.

Phase 8B's separate positive-verified-flags Completion shortcut must not be
included in only one arm. The primary comparison is B0/C0. Gold, family and
oracle rationale must never enter local model state, criteria or instructions.

## Freeze and execution order

1. Author 80 cases, oracle sets, simulation narrative and this protocol.
2. Freeze exact SHA-256 of case JSONL, generator, runner and this protocol
   in a manifest with no predicted labels.
3. Commit all frozen sources and manifest to Git BEFORE loading Laya. Require
   a full ancestor freeze commit SHA; the runner verifies archived Git bytes
   match the manifest and live files before model inference.
4. Run a single local-only replay using the already cached pinned checkpoint
   convaiinnovations/laya-typed-decisions at revision
   f9ab0b228f0fc0f14d873dbc99038f135c2da1b2, with backend MLX. Do not
   download a model or call any real main-model Provider.
5. Record ALL predictions and failed model attempts, do not drop tough cases
   or rerun to optimize the score. Group by gate × source × split. Report
   opportunity eligibility, actual model calls, guarded vs raw decisions,
   paired correctness discordance, acceptable/preferred accuracy, safety and
   verification errors, local inference latency and null native outcomes.
6. New hypotheses, thresholds, tests or oracle changes require a separately
   frozen NEW cohort, not retroactive edits to this holdout.

## Predeclared limitations and hard stops

- This is a newly authored, never previously scored *synthetic* set, not
  independent real-world outcomes or external human adjudication.
- Editorial scenarios have correlated design assumptions and deliberate
  oversampling of unusual failures. No production accuracy/harm-rate claim.
- 40 samples per Gate and fewer eligible model calls: report small support.
- Laya checkpoint confidence is not guaranteed calibrated.
- Token/provider cost savings and end-to-end Agent performance are NOT
  MEASURED in Shadow-only offline replay.
- Actual retry, auto-complete, paid escalation and changing production
  Hermes / DSH configuration remain strictly prohibited.
- Real StepFun stepfun/step-5-preview + Laya native Shadow E2E requires
  separate explicit physical request, time and paid budget authorization.
