# Local System One Phase 8C — Retry / Escalation Gate Final Report

**As-of:** 2026-10-14 (Asia/Shanghai). **Scope:** experimental, opt-in Shadow-only.
**Overall:** Engineering Acceptance **BLOCKED** / Model Quality **NO-GO** /
Active Readiness **NO-GO**.

The code and offline pilot can be technically useful without establishing
independent native Agent E2E, production safety or genuine model generalization.

## 1. Repositories, versions and isolation

- Baseline GitHub \`main\`: \`ca9d671986dcfc1f4a06931069694d161f6370ac\`
  (Phase 8B PR #4 already merged).
- NAS \`origin/main\` observed \`afa2512cc66400d111c28cb5fe00e9f83fdba49a\`;
  separate NAS 8B branch tip \`527f031da038d55573ea1f7104b37e042b397b50\`.
  The two main branches were not assumed identical or force-reset.
- Phase 8C starts in an isolated worktree from current **public** \`main\`,
  branch \`feat/phase8c-retry-escalation-shadow\`; no production profile changes.
- Installed Hermes at audit: \`v0.21.7+495.g6e7b83a\`, commit
  \`6e7b83a2f1c093e992a8d838ed77ea320fbd8e51\`.
- Inspected DSH upstream: \`0.1.7-rc.2\` pin
  \`477b4f420553e8a52c2fbccc464d7561b239c443\`; other peer-range
  versions not independently revalidated.
- New source adapter versions: Hermes \`0.9.0\`, DSH \`0.6.0\`.
  These are **source updates**, not an automatic installation or upgrade.

## 2. Native failure hooks and failure taxonomy

The findings are in [PHASE8C_FAILURE_AUDIT.md](PHASE8C_FAILURE_AUDIT.md).
Hermes emits terminal \`post_tool_call\` with tool IDs, status and error type;
DSH emits \`session/event\` \`tool/call\` + \`tool/result\` with explicit
\`isError\`, tool IDs and optional \`error.code\`. Neither supplies an
authoritative original-operation execution outcome or verified per-call
retry budget. Both lack dependable full provider-failure coverage through
these hooks. Missing evidence is \`unsupported\`, not inferred from error text.

Typed categories: timeout, network, rate_limit, server_error, auth,
validation, tool_error, test_failure, logic_failure, partial_success,
unknown. DSH and Hermes expose different native data and are not treated
as interchangeable replay formats.

## 3. Six decision semantics and hard safety

Advice only: \`retry_same\`, \`try_alternative\`, \`escalate_model\`,
\`verify_state\`, \`ask_user\`, \`abort\`.
The first-class \`verify_state\` result is mandatory when a possible
non-idempotent side effect has unknown outcome. Applied writes never get
repeat-action authority. HTTP 401/403 require permission recovery; HTTP 429
may recommend waiting only when both the trusted Retry-After and caller
budgets are present. Exhausted budgets cannot retry. Approval cannot be
invented. Unknown history budgets are null/unavailable, not infinite.

A safe set of options is built by deterministic rules **before** asking
Laya; model output outside that set is replaced with a conservative rule.
The Runtime retains \`raw_model_decision\`, \`guarded_decision\`,
\`decision_source\` and \`safety_override_reason\`. No rule or model action
actually retries, switches provider, approves, aborts or edits native state.

## 4. Runtime, Contract and integration changes

Runtime: \`POST /v1/workflows/retry-escalation-gate\`; strict bounded
typed-only input schema, request ID, model or rule metadata, decision
probabilities when model used, latency, advisory marker. Unknown text fields
such as full trace, raw log or credential are rejected. Failures at the
observer boundary fail open without affecting original Agent actions.

Adapter Contract v1.0: additive **opt-in** gate \`retry_escalation\`, six
enum decision values, typed envelope, Action Outcome and telemetry.
Older strict client versions might reject a newly delivered enum:
new retry envelopes are never sent unsolicited; both feature flags default OFF.
Completion Gate wire semantics and authority remain unchanged.

Hermes: independent \`post_tool_call\` Shadow observer, explicit failure-only
status, limited pinned tool operations, 2 observations per turn,
4 nonblocking daemon workers; metadata-only bounded history and session
cleanup. DSH: native tool/call-ID pairing with \`tool/result.isError\`,
matching limits and isolated per-turn/session state. Unknown tools are
\`unsupported\`. The two adapters do not consume Completion \`continue\`
as a retry signal.

## 5. Real HTTP transport and Shadow observations

An isolated, short-lived loopback MLX Runtime was launched for a controlled
synthetic event replay with a disposable HTTP server; no production gateway,
credentials or actual external writes were involved:

| Probe | Result | Evidence limit |
|---|---|---|
| Runtime hard verification over HTTP | PASS | synthetic unknown write |
| Runtime actual MLX choice over HTTP | PASS | synthetic safe read |
| Hermes adapter hook → Runtime HTTP | PASS | native hook-shaped replay, **not** native Agent |
| DSH adapter event → Runtime HTTP | PASS | upstream event-shaped replay, **not** provider-backed Agent |
| Hermes one hook callback overhead | 1.501 ms | one synthetic warm nonblocking callback; not P95 or Agent end-to-end |
| Full Hermes provider-backed Agent E2E | NOT MEASURED | independent profile + provider/task required |
| Full DSH provider-backed Agent E2E | NOT MEASURED | independent native task not executed |

Runtime unavailable, invalid JSON/decision, capacity saturation and unknown
tool identity were tested as **fail-open / unsupported**, with no native
call interception. This is transport and lifecycle feasibility, not
Agent failure recovery effectiveness.

## 6. Benchmark provenance and model-vs-rules

Protocol: [PHASE8C_EVALUATION_PROTOCOL.md](PHASE8C_EVALUATION_PROTOCOL.md).
Three frozen public synthetic splits, 30 rows each, 5 cases for each of six
decisions. Every split has its own SHA256 in that protocol. **0 real task
cases, 0 separately human-adjudicated production outcomes**. Synthetic
gold labels and feature templates come from the same author/generator,
so even the frozen holdout is not an independent real blind set.

- **A Native Agent:** NOT MEASURED, no matched task-success, token,
  tool-call count, or actual savings data.
- **B Rule-only:** deterministic hard rules + conservative ambiguous fallback.
- **C Rules + Laya:** same hard rules, model chooses among permitted options.

| Split (synthetic n=30) | B Accuracy / Macro F1 | C MLX Accuracy / Macro F1 | MLX choice calls | Delta accuracy |
|---|---:|---:|---:|---:|
| Calibration | 66.67% / 0.5833 | 100% / 1.0000 | 15 | +33.33 pp |
| Frozen synthetic holdout | 66.67% / 0.5833 | 100% / 1.0000 | 15 | +33.33 pp |
| Adversarial structural | 66.67% / 0.5648 | 93.33% / 0.9352 | 15 | +26.66 pp |

**Interpretation:** The synthetic score is encouraging for typed selection,
but heavily structured, formulaic features make these numbers unsuitable
as claims about real Agent recovery. In particular, the benchmark's gold
label for \`escalate_model\` represents synthetic adviser preference,
not observed benefit from spending more on an LLM. Laya's incremental
value on independent real failures remains **UNPROVEN**.

## 7. Safety and uncertainty

| Metric | Calibration | Holdout | Adversarial | Interpretation |
|---|---|---|---|---|
| Unsafe Retry Rate, B and C | 0/10 | 0/10 | 0/10 | each 95% Wilson upper bound 27.75% |
| Missed Verification Rate, B and C | 0/5 | 0/5 | 0/5 | each 95% Wilson upper bound 43.45% |
| Verify State Recall, B and C | 100% | 100% | 100% | tiny synthetic denominator |
| Unnecessary Escalation | 0/30 | 0/30 | see machine-readable report | no true external cost observed |

Safety-dominated cases were largely determined by deterministic rules.
Zero unsafe suggestions in 10 synthetic unsafe cases is **not** an active
authorization safety guarantee. Do not interpret these deliberately enriched
samples as production failure or attack base rates. Six-class confusion
matrices and precision/recall are preserved in the public processed JSON.

## 8. Backend agreement, latency and cost

Isolated **real MLX** model-path local wall timing (not native Agent overhead):

| Split | MLX model-path P50 | P95 |
|---|---:|---:|
| Calibration | 61.000 ms | 120.390 ms |
| Holdout | 60.434 ms | 61.701 ms |
| Adversarial | 61.512 ms | 67.779 ms |

The installed Laya checkpoint emitted a temperature-clamping warning;
choice confidence must be treated as **uncalibrated**. There was no power
measurement or actual LLM token bill reduction in this Shadow pilot.

**ANE/MLX agreement: NOT MEASURED for 8C.** Attempting to load the installed
published flexible Core ML \`model.mlpackage\` with the existing research
L512 ANE runtime failed manifest verification: it expects a verified
\`laya-ane-research\` fixed B1/L512/K32 artifact and adjacent
\`manifest.json\`, whereas the locally available published package has a
different \`laya-coreml\` flexible format. No verification bypass or
fabricated ANE prediction was used. 8B historical agreement is not reused
as 8C evidence. Correct next step: produce or locate a legitimately
manifested research L512 artifact and repeat **the frozen** cases without
modifying gold labels.

## 9. Failure injection, privacy and regression testing

- Python new Gate, contract and HTTP tests: strict schema and injection,
  permissions, rate limits, duplicate writes, applied side effects,
  exhaustion, candidate filtering, malformed JSON, local HTTP authentication.
- Hermes: default OFF, no false-success triggers, unknown-tool unsupported,
  nonblocking per-turn dedup, session cleanup, thread saturation fail-open,
  malformed Runtime response and secret-bearing fake error inputs excluded.
- DSH: equivalent OFF/Shadow, exact call ID join, error-only policy, bounded
  observations, turn isolation, malformed response fail-open, metadata-only.
- Both client adapters: real loopback Runtime inference and Shadow observation,
  never native provider E2E.
- Python whole-tree tests: **382/382 PASS**, including existing Gate regressions,
  Retry failure injection, HTTP and synthetic corpus integrity checks.
- DSH Vitest: **50/50 PASS**; TypeScript typecheck and build PASS.
- Hermes native `plugins validate --json`: PASS on manifest, hooks,
  capability registration, native ABI and safety scan. Validator also
  reported existing private-core-import compatibility warnings; this
  gate did not introduce a new private integration hook.
- Public allowlist release preview: content sanitizer PASS; the pre-commit
  preview correctly reports `publish_ready: false` while Git is dirty.
  Final clean-tree release must be checked again after commit.
- No genuine provider-backed Agent E2E; no production recovery enabled.

## 10. Files, publication and review

New files include:
\`local_system_one/workflows/retry_escalation_gate.py\`,
\`integrations/deepseek-harness/local-system-one-dsh/src/retry.ts\`,
\`benchmarks/retry/*\`,
\`docs/PHASE8C_FAILURE_AUDIT.md\`,
\`docs/PHASE8C_EVALUATION_PROTOCOL.md\`,
\`docs/RETRY_ESCALATION_GATE.md\`,
new Python/TypeScript tests, and processed synthetic report.
Updated existing files include Runtime routing, adapter contract/schema,
Hermes/DSH plugin config and lifecycle implementation, and public allowlist.
Existing Completion thresholds/Gold Set/results were not edited.

Branch: \`feat/phase8c-retry-escalation-shadow\`.
**Development commit SHA, sanitized publication commit SHA, GitHub PR URL,
Codex Review disposition, exact final test counts and sanitizer status will
be recorded from the actual checked artifacts. Do not call review PASS or
merge without evidence.**

## 11. Independent acceptance decisions

- **Engineering Acceptance: BLOCKED.** Source and isolated transport work
  are not a substitute for two independently observed provider-backed native
  Agent E2E tasks with verifiable outcomes.
- **Model Quality: NO-GO.** Model beats this formulaic synthetic rule
  baseline but lacks independent real labels, robust calibration and 8C
  ANE/MLX verification. Safe net value not established.
- **Active Readiness: NO-GO.** No automatic retry/abort, model/provider
  upgrade, authority change, approval bypass or side-effecting recovery.

## 12. Next independent phase

Collect genuine Hermes and DSH failed-tool events **with only privacy-safe
structured metadata**, plus verified operations and external outcomes;
independently adjudicate label/side-effect truth and hold out future unseen
failure families. Expose trustworthy attempts, budget/approval and
idempotency-key metadata through separately audited adapter policies rather
than string parsing. Reproduce ANE using a verified matching L512 artifact.
Only then evaluate whether Laya provides safety-adjusted benefit over
deterministic rules in controlled paired Agent tasks. If that benefit remains
absent, keep Recovery rule-only rather than escalating into Active.
