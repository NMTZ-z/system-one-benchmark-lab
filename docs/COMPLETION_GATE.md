# Completion Gate

Phase 8A adds a platform-independent Completion Gate to Local System One. Its only question is:

> Is the current user task complete, should the Agent continue, or should it verify the apparent result before stopping?

The Gate is **Shadow-only in Phase 8A**. It never terminates an Agent loop, suppresses a tool call, skips verification, emits a final answer, or forces a retry.

## 1. Semantics

The Runtime returns exactly one semantic value:

```text
complete | continue | verify
```

- `complete`: the requested deliverable is satisfied, required checks are complete, and no important unresolved blocker remains.
- `continue`: substantive work is missing, a required step/artifact is absent, a blocking tool action failed, or an explicit required test failed.
- `verify`: a plausible result exists, but its final state, evidence, or required independent validation is not yet established.

A false `complete` is treated as more dangerous than a false `verify` or `continue`.

## 2. Runtime API

```text
POST /v1/workflows/completion-gate
```

Minimal request:

```json
{
  "task": "Confirm the release is published.",
  "current_result": "A release record exists, but remote state was not checked.",
  "execution_state": {
    "verification_required": true,
    "final_state_verified": false
  },
  "request_id": "turn-123"
}
```

Representative response:

```json
{
  "workflow": "completion_gate",
  "decision": "verify",
  "decision_source": "rule",
  "reason": "final_state_not_verified",
  "probability_complete": 0.0,
  "probability_verify": 1.0,
  "probability_continue": 0.0,
  "confidence": 1.0,
  "backend": "rule",
  "request_id": "turn-123"
}
```

The response also includes route/latency metadata, token count, input-bounding metadata, and ANE health metadata.

## 3. Compact completion context

Completion does not accept a raw transcript or Agent trace. The request surface is intentionally small:

```text
task
current_result
execution_state
request_id?
```

`task` is bounded to 4,000 characters and `current_result` to 6,000 characters. Longer values are truncated locally before model inference. Unknown top-level fields are rejected.

Supported structured execution state is platform-neutral:

```text
tools_used
tool_failures
tests_run
tests_passed
artifacts_created
required_checks_completed
required_artifact_missing
required_step_missing
blocking_failure
conflicting_evidence
verification_required
final_state_verified
```

Counts must be non-negative integers, booleans must be booleans, and `tests_passed` cannot exceed `tests_run`.

## 4. Deterministic rules

Phase 8A deliberately uses only conservative rules.

Hard `continue`:

- `blocking_failure=true`;
- `required_artifact_missing=true`;
- `required_step_missing=true`;
- `required_checks_completed=false`;
- `tests_passed < tests_run` when explicit test counts are supplied.

Hard `verify`:

- `conflicting_evidence=true`;
- verification is required but the final state is not verified.

There is no broad hard-`complete` rule in Phase 8A.

## 5. Typed-decision fallback

Cases not resolved by a deterministic rule use the existing Laya typed `choice` primitive with three labels: `complete`, `verify`, and `continue`.

The Runtime applies an additional safety guard: a model-selected `complete` with `probability_complete < 0.70` is downgraded to `verify`. Model errors or invalid labels conservatively return `continue`; this prevents classifier failure from creating a silent premature stop.

The current Laya checkpoint reports a warning that some shipped temperature values are clamped, so affected confidence values should be treated as uncalibrated. Phase 8A therefore does not treat model confidence as execution authority.

## 6. Adapter Contract v1

Completion is a backward-compatible extension of Adapter Contract `1.0`; no major or minor schema-version bump is required.

Canonical Completion decision payload:

```text
gate = completion
value = complete | continue | verify
probability_complete
probability_verify
probability_continue
```

No Hermes or DeepSeek Harness lifecycle object, provider field, tool name, or stop command enters the shared contract. Runtime defines semantic meaning; each Adapter owns platform lifecycle and any future execution mapping.

## 7. Hermes Shadow integration

Hermes adapter `0.8.0` observes Completion through audited real Hermes hooks:

```text
pre_llm_call   -> bounded task
post_tool_call -> tool/failure counters
post_llm_call  -> bounded current result
on_session_end -> one Completion observation
```

`on_session_end` exposes `completed`, `failed`, `interrupted`, and `turn_exit_reason`, making it a stable one-per-turn observation boundary. It is intentionally too late to grant stop authority in Phase 8A.

Completion state is process-local and bounded. Persisted plugin state contains only decision metadata and task/result character counts, never the raw task or final response. A dead/unreachable Runtime records `failed_open`; Hermes behavior is unchanged.

## 8. DeepSeek Harness Shadow integration

DSH adapter `0.5.0` uses the audited DSH lifecycle:

```text
agent/pre-step  -> bounded turn task
assistant/message -> bounded current result
tool/result     -> tool/failure counters
turn/end        -> one Completion observation
session/end or session/close -> cleanup
```

The Adapter keys ephemeral state by session + turn and removes it at the turn/session boundary. Completion has no mutation hook and cannot veto the completed turn. A dead or malformed Runtime fails open to native DSH behavior.

Hermes and DSH intentionally use different hooks where their native lifecycles differ. The portable requirement is semantic consistency, not hook-name symmetry.

## 9. Telemetry and privacy

Comparable Completion telemetry includes:

```text
platform
adapter_version
gate = completion
mode
decision
decision_source
reason
backend
latency_ms
confidence
action_status
action_reason
request_id
```

Phase 8A normally records `action_status=observed`. Integration failures use `failed_open`; unavailable platform context may use `unsupported`.

Normal telemetry must not persist API credentials, auth headers, system prompts, full transcripts, full task/result bodies, raw tool logs, or private Agent history.

## 10. Gold set

Public benchmark: `benchmarks/completion/gold_v0.1.jsonl`

The first public set has 120 balanced labeled cases:

| Source | complete | continue | verify | Total |
|---|---:|---:|---:|---:|
| real | 10 | 10 | 10 | 30 |
| synthetic | 30 | 30 | 30 | 90 |

The `real` slice is a privacy-safe reconstruction of tasks and observed outcomes from public repository engineering work. It is **not** a dump of private Hermes/DSH transcripts. The synthetic slice broadens boundary coverage. Metrics are reported separately and are never combined into one headline score.

Rebuild and evaluate with:

```bash
.venv/bin/python benchmarks/completion/build_gold_set.py
.venv/bin/python benchmarks/completion/evaluate.py \
  --url http://127.0.0.1:8787/v1/workflows/completion-gate \
  --out results/processed/completion-gate-v0.1.json
```

`evaluate_live_backend.py` is also provided for validating the current CompletionGate implementation against an already-running Local System One generic `/v1/choice` backend without replacing that service process.

## 11. Phase 8A benchmark result

The recorded Phase 8A run used the current CompletionGate implementation with the existing healthy Local System One ANE-backed generic choice endpoint. Rules ran locally; model-only cases were delegated to the real Laya typed-decision backend with `backend=ane`.

### Real slice, n=30

- accuracy: **63.33%**
- macro F1: **0.5308**
- premature completion rate: **0 / 20 = 0.00%**

| truth \\ predicted | complete | continue | verify |
|---|---:|---:|---:|
| complete | 0 | 0 | 10 |
| continue | 0 | 9 | 1 |
| verify | 0 | 0 | 10 |

Per-class recall: complete `0.00`, continue `0.90`, verify `1.00`.

### Synthetic slice, n=90

- accuracy: **63.33%**
- macro F1: **0.5308**
- premature completion rate: **0 / 60 = 0.00%**

| truth \\ predicted | complete | continue | verify |
|---|---:|---:|---:|
| complete | 0 | 0 | 30 |
| continue | 0 | 27 | 3 |
| verify | 0 | 0 | 30 |

The key finding is not the headline accuracy. The 0.70 safety threshold prevented every premature `complete`, but it also downgraded every labeled `complete` case to `verify`. This is acceptable evidence for a conservative Shadow phase, but it is not acceptable for Active automatic stopping.

The threshold was **not** tuned on this gold set after seeing the result. That would turn evaluation into decoration.

## 12. Fail-open behavior

There are two distinct safety layers:

1. Runtime classifier failure: Completion returns conservative `continue` rather than a false `complete`.
2. Adapter/HTTP integration failure: the platform Adapter records `failed_open` and preserves native Hermes/DSH behavior.

A Completion failure never receives authority to terminate or mutate the Agent loop in Phase 8A.

## 13. Known limitations

- The current 0.70 complete threshold is over-conservative on the first public benchmark: complete recall is zero.
- The public `real` slice is reconstructed from public engineering outcomes rather than raw private Agent-history replay.
- Phase 8A observes at the end boundary. A future Active design needs an earlier execution-loop decision point and separate proof that it cannot suppress required verification/tool work.
- Adapter-produced execution state is intentionally minimal; higher-level orchestration can eventually provide richer task-specific required-check/artifact facts.
- No confidence calibration claim is made for the current Laya checkpoint.

## 14. Active routing policy

**Active Completion: NO-GO for Phase 8A.**

Reasons:

1. the phase is explicitly Shadow-only;
2. the current lifecycle integration is designed for observation, not pre-stop interception;
3. although premature completion is zero on the first gold set, complete recall is also zero;
4. the public real set is too small to establish production stop safety.

The appropriate next step is a Completion-specific calibration/replay phase, not a broad Agent planner and not an unrelated new Gate.
