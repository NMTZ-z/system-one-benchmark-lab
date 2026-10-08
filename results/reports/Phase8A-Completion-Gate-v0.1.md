# Phase 8A — Completion Gate Validation Report

## Verdict

**PHASE8A_PASS** for Shadow-only implementation and evaluation.

**Active Completion: NO-GO.**

Phase 8A adds the platform-independent `complete | continue | verify` decision, a Runtime workflow endpoint, Adapter Contract v1 extension, Hermes `0.8.0` Shadow integration, DSH `0.5.0` Shadow integration, privacy-safe telemetry, fail-open behavior, and a 120-case public benchmark.

## Benchmark corpus

`benchmarks/completion/gold_v0.1.jsonl`

- 30 privacy-safe public-repository outcome reconstructions: 10 per class.
- 90 synthetic boundary cases: 30 per class.
- Source slices are evaluated separately.
- No private Agent transcript, raw system prompt, credential, or tool log is included.

## Result

### Real, n=30

- accuracy: 0.6333
- macro F1: 0.5308
- premature completion rate: 0/20 = 0.0000
- complete recall: 0.0000
- continue precision / recall: 1.0000 / 0.9000
- verify precision / recall: 0.4762 / 1.0000

Confusion matrix:

| truth \\ predicted | complete | continue | verify |
|---|---:|---:|---:|
| complete | 0 | 0 | 10 |
| continue | 0 | 9 | 1 |
| verify | 0 | 0 | 10 |

### Synthetic, n=90

- accuracy: 0.6333
- macro F1: 0.5308
- premature completion rate: 0/60 = 0.0000
- complete recall: 0.0000
- continue precision / recall: 1.0000 / 0.9000
- verify precision / recall: 0.4762 / 1.0000

Confusion matrix:

| truth \\ predicted | complete | continue | verify |
|---|---:|---:|---:|
| complete | 0 | 0 | 30 |
| continue | 0 | 27 | 3 |
| verify | 0 | 0 | 30 |

## Interpretation

The current `probability_complete >= 0.70` guard is deliberately conservative. It produced zero premature completion in this set, but every labeled complete case was downgraded to verify. This is useful Shadow evidence and a clear reason not to activate automatic stopping.

The threshold was not changed after observing the gold-set result.

## Runtime and lifecycle validation

- New endpoint: `POST /v1/workflows/completion-gate`.
- Valid request live-smoked against the current checkout with the real MLX runtime; a low-probability model complete was safely downgraded to verify.
- Hermes real hook API was audited on installed Hermes `0.21.5`; multiple callbacks per hook are supported and `on_session_end` exposes completion/failure/interruption state.
- DSH pinned lifecycle source was audited; `assistant/message`, `tool/result`, and `turn/end` provide the required observation boundary.
- Both Adapters remain observation-only and preserve native behavior on Runtime failure.

## Automated validation

Focused Python validation during development: 49/49 passed.

DSH validation during development: 40/40 tests passed, `tsc --noEmit` passed, production build passed.

Final validation:

- full Python repository suite: **103/103 passed**;
- DSH adapter: **40/40 passed**;
- DSH TypeScript typecheck: passed;
- DSH production build: passed;
- `npm audit --audit-level=high`: **0 vulnerabilities**;
- Hermes `plugins validate`: passed, including hook/capability/security checks;
- Hermes `plugins doctor --ci`: passed for adapter `0.8.0`, with 7 hooks registered;
- `git diff --check`: passed;
- public gold/result JSON parse and privacy-key audit: passed.

## Privacy

The public benchmark output stores only case IDs, source type, labels, predictions, decision metadata and latency/confidence. It does not persist task/result bodies. Adapter telemetry similarly stores metadata/lengths rather than raw task or response content.

## Active decision

`NO-GO` until a later Completion-specific phase gathers a larger real Shadow set, calibrates the complete boundary independently, and validates an earlier lifecycle point appropriate for stop authority.
