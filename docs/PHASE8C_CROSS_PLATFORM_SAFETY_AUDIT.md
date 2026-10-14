# Phase 8C — Cross-platform safety audit and Codex P2 closure

**Scope:** Local System One Retry / Escalation Gate, Hermes adapter, DeepSeek
Harness adapter and Adapter Contract v1. **Status:** source/test audit only;
release and Codex re-review are independent gates.

## Why this audit exists

The first three Codex reviews on GitHub PR #5 found seven P2 defects. Several
were the *same invariant* violated by different adapters. A passing benchmark
accuracy score does not establish a safe concurrency or accounting boundary.
This audit maps every defect to executable regression evidence, then checks
the shared contracts rather than relying only on the originally commented line.

## The seven findings and their regression guards

| Review / finding | Invariant | Code guard | Executable evidence |
| --- | --- | --- | --- |
| R1: mutating type masquerades as a side-effect-free read | `write`, `git_push`, `pr_create` cannot claim `side_effect=none` | `RetryEscalationRequest.from_payload` | `test_phase8c_review_rejects_contradictory_mutation_metadata`, HTTP 400 mutation test |
| R1: unsafe-retry denominator omits auth/time exhaustion | Every explicitly forbidden `retry_same` contributes to the denominator, independent of the prediction | `benchmarks/retry/evaluate.py:is_unsafe_to_retry` | `test_review_all_blocked_retries_are_counted_in_each_frozen_split`, `test_review_injected_bad_retry_on_401_403_and_zero_time_is_detected` |
| R2: hard-rule decisions absent from metrics | Rule-only requests are metered; completed inference is not double-counted | `RetryEscalationGate._rule_result` | `test_rule_paths_increment_metrics_once_without_running_model`, `test_model_path_and_safety_override_do_not_double_count_metrics`, HTTP `/metrics` test |
| R2: DSH eviction resets an active turn's two-observation limit | Never evict an active safety counter at capacity | DSH `retryCounts` capped at 96 active turns | 96/97-turn overflow, oldest-turn third failure and duplicate-start Vitest |
| R3: direct engine failure is counted twice | An entire Gate call shares the nested error-accounting context | `RetryEscalationGate.decide` wraps `error_accounting_scope` | `test_real_decision_engine_failure_is_counted_once_per_direct_request` (same exception reused across two calls) |
| R3: Hermes eviction resets an active turn's limit | Keep the 64 active session/turn counters until native session end; do not conflate sessions sharing a turn ID | Hermes Retry observer uses `(session_id, turn_id)`, 64-capacity admission, cleanup by session | `test_retry_concurrent_65th_turn_never_evicts_live_safety_counter`, `test_retry_session_identity_isolated_for_matching_turn_ids`, missing-session fail-open |
| R3: Python contract silently converts missing required fields into null | A required nullable field must be **present** and type-correct | `validate_decision_envelope`, `envelope_from_runtime`, Hermes response validator | `test_retry_envelope_required_nullable_fields_cannot_be_missing`, `test_retry_runtime_normalization_never_fabricates_required_fields`, Hermes and DSH receiver tests |

## Shared constraints verified across modules

1. **Permissions and effects:** Neither adapter infers a write succeeded or
   did not happen from raw logs. Unknown effects require `verify_state`, and
   user approval / exhausted budgets cannot authorize `retry_same`.
2. **Bounded observation:** Hermes uses at most 2 failure observations per
   active `(session, turn)`, at most 64 tracked active turns and 4 nonblocking
   observer workers. DSH uses at most 2 observations per `(session, turn)`,
   at most 96 tracked active turns and 4 in-flight requests. At capacity the
   **new** observation is rejected, not the older live safety state. Both
   retain duplicate-call suppression and explicit end-of-lifecycle cleanup.
3. **Error accounting:** A nested Engine error is counted once per external
   Gate call, even on direct Python calls and when the same exception object
   is rethrown by two different requests. Completed model inference is not
   counted a second time due to a guarded recommendation.
4. **Wire contracts:** The runtime emits both `raw_model_decision` and
   `safety_override_reason` explicitly, using JSON null when appropriate.
   The Python envelope validator and runtime normalizer refuse their absence;
   the Hermes/DSH response validators also refuse missing fields. The
   top-level `request_id` is also required-but-nullable, optional `confidence`
   and `metadata` reject explicit null, and non-null request IDs / override
   reasons have matching nonempty-string schema bounds. Python and JSON
   Schema agree on these required, nullable and nonempty semantics.
5. **Privacy:** Retry payloads remain structured failure/operation/history/
   constraints metadata. Error text, arguments, secret-bearing result bodies,
   provider credentials and native tool action handles do not enter the Gate
   or its telemetry. Synthetic identifiers only in regression fixtures.
6. **Authority and compatibility:** OFF remains the default; Shadow is
   advice-only. No automatic retry, write, abort, provider/model escalation,
   approval bypass or production-config mutation has been added. Existing
   Completion Gate threshold/contract and frozen synthetic benchmark SHA256
   are not altered by this audit.

## Deliberate safety trade-offs

- When all 64 Hermes or 96 DSH tracking slots are active, future untracked
  turns are **not observed** until slots are released. This prioritizes safety
  and bounded memory over Shadow coverage; it must not be reported as a
  successful classification.
- If the native lifecycle never emits the expected session-end event, an
  active Hermes safety counter is retained until the plugin instance ends.
  Exhausting the pool causes advisory observations to fail open, **not** a
  forced deletion that would reset the two-observation safety budget. The
  native hook's event shape/lifecycle should be confirmed in provider-backed
  E2E before extending coverage.
- DSH tracks matched upstream call IDs. Its separate bounded pre-call name
  cache can evict an unmatched tool name under exceptional load; a missing
  name is `unsupported` rather than guessed, with no unauthorized retry.
- The MLX synthetic split and formulaic labels cannot establish real
  generalization, rate of harmful retries, cost savings or actual Agent
  recovery effectiveness. MLX confidence is not calibrated, and a verified
  fixed-L512 ANE artifact is still missing.

## Release gate

An independent clean-tree public bundle/sanitizer run, complete Python/DSH
regressions, Hermes plugin validation and GitHub Codex re-review must be
reported with actual outcomes and commit SHA. **Passing all source-level
checks is not the same as Engineering Acceptance:** real Hermes + DSH
provider-backed Agent E2E and independently adjudicated task outcomes remain
missing. Keep **Engineering Acceptance: BLOCKED**, **Model Quality: NO-GO**
and **Active Readiness: NO-GO** until those separate gates are satisfied.
