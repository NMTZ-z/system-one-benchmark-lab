# Phase 8.2A — Native Agent Shadow E2E: bounded exploratory run

**Status: ENGINEERING BLOCKED — not a dual-platform native E2E PASS.**  This
report records genuine provider-backed Agent executions alongside their exact
missing evidence. It does **not** extrapolate Hook Replay or direct Runtime HTTP
into native Agent E2E. The deterministic rules, Laya model calibration, ANE,
Active authority and model comparisons are outside this phase.

## 1. Baseline, independence and execution provenance

- Public GitHub `main` checked on 2026-10-18: `da2947a2091570a28a061d651200eec3d94276df`, with no open PR at start.
- NAS `origin/main` was `afa2512cc66400d111c28cb5fe00e9f83fdba49a`; **it was not updated or reset**. Another worktree contained an unrelated untracked `uv.lock` and was left alone.
- Isolated branch: `feat/phase8-2a-native-shadow-e2e`, based on the public SHA above. Source/test runs below were exploratory **before this phase's fix was frozen in Git**, and must not be used as a formal post-fix acceptance run.
- Installed Hermes: `v0.22.1+11.gd923a5e`, local `d923a5eb487a`. Isolated temporary profile: `p82native`. Original provider and production profiles were not changed. Adapter installed in the isolated profile from the full public base commit, version `0.9.0`.
- DeepSeek Harness native `headless` source: pinned `0.1.7-rc.2` at `477b4f420553e8a52c2fbccc464d7561b239c443`; DSH adapter `0.6.0` built from the public main source. No generic custom event emitter was substituted for the platform.
- Main model: an **actual authorized remote provider** `nova/deepseek-v4-flash`, both platforms. Decision model: `laya-typed-decisions` / **MLX**, isolated loopback Runtime port 18782. These are different models. JEV/TypeSafe was not invoked; no Active modes were granted.
- Shadow config only: Completion end-of-turn and opt-in tool-result probe; Retry separately opt-in; Search, Model Tier, Notification and Canary disabled. Logs, test tasks and full native traces were confined to a Git-ignored private directory. No plaintext secrets entered the repo or CLI arguments.

Prior Phase 8B/8C reports cover mocked lifecycle replay and direct Runtime HTTP,
but no dual-platform provider-backed Completion/Retry E2E. Those results were
not reused as current successful runs.

## 2. Four core attempts and independent outcomes

| Run | Platform / native event | Independent business outcome | Observer/runtime evidence | Classification |
|---|---|---|---|---|
| H-S1 | Hermes main-model-driven `read_file`→`write_file` | Output exists, but one trailing newline missing; **SHA differs** | Native plugin stored tool-result and session Completion; `backend=mlx`, `decision_source=model`, Shadow observed | **Artifact mismatch**, genuine Completion integration evidence, not success PASS |
| H-S2 | Hermes main-model-driven `read_file`→`write_file` | **Exact content and SHA match**, output generated in isolated directory | Native plugin stored tool-result and session Completion; MLX/model observed; no Active authority | **Exploratory success** (not post-fix frozen acceptance) |
| H-F1 | Hermes main-model-driven `read_file` on a known-nonexistent path | File remains absent; Agent correctly reports failure, no shadow-driven recovery | Native Completion tool probe observed `tool_failures=1`; Retry recorded **`unsupported/operation_unverified`** rather than calling Runtime | **Native failure event observed; Retry integration not passed** |
| D-S1 | DSH native `headless` provider-backed tool call and result, completed turn | **Output file exists and matches predetermined content**, independent of final answer | DSH native trace captures `tool_call`, `tool_result`, `step_end`, `turn_end`; no attributable successful Completion→Runtime evidence retained | **Platform tool task success; observer E2E PARTIAL** |
| D-S2 | DSH second native write and tool result | Output verified; final DSH turn **failed with Provider 429/QUOTA** | Loopback collector recorded **two Completion POSTs with HTTP 503** after its owning Runtime session timed out | **Tool succeeded, turn not completed, failed-open observation only** |
| D-F1 | DSH planned native failed read | **Not run**: remote provider reached a quota error | No native failure event / Retry Shadow result | **BLOCKED**, not replayed as a substitute |

An allowlisted public summary is available in
`results/processed/phase8_2a_native_shadow_exploratory.json`. It explicitly
marks raw private provenance and incomplete acceptance.

The DSH initial `stepfun` launch failed before a provider request because the
frozen upstream did not have that route registered (`NO_ADAPTER`). A minimal
*private* DSH `llm-pi-ai` provider declaration for the already-authorized
Nova route resolved the launcher issue. It did not change upstream code,
production providers or the published adapter.

**Counts:** three Hermes provider-backed runs (8 successful provider calls);
DSH D-S1 had 2 successful LLM steps; D-S2 had 1 successful step plus 1 failed
429 request. Thus **at least 12 attempted main-model calls**, counting the
failed request; the authoritative billing count and cost are unknown. No paid
DSH read-failure test was launched after the QUOTA error. Original cap 12 calls
was explicitly raised to 18 for bounded investigation of the observed native
incompatibility, **without raising the RMB 2 monetary ceiling**. Usage reported
by Hermes `estimated_cost_usd=0.0` is not verified actual pricing or spend.

**Independent verification:** H-S1 failed a byte-for-byte hash check, even
though the Agent said it had succeeded. H-S2 passed the same check. D-S1 and
D-S2 each produced the exact, separately checked test-file content; DSH's
native event stream has one paired tool call/result per task, and typed Turn
boundaries. D-S2 cannot count as a completed Agent task. The originally absent
files remained absent; no production resources were used as test targets.

## 3. Real compatibility bug found, isolated repair

Hermes `v0.22.1` supplies `tool_name` in its actual native
`post_tool_call` hook (the frozen source shows `invoke_hook(..., tool_name=...)`).
The existing Retry observer used only `function_name`, which the older
constructed tests populated. H-F1 therefore correctly reported
`operation_unverified` under the old implementation. This was a genuine
integration gap, not a missing budget or a model classification issue.

The phase's small fix accepts native `tool_name`, retains `function_name` for
older host/fixture compatibility and rejects conflicting dual identities as
unsupported. A regression asserts the positive native path, the negative
conflict path, no forwarding of raw tool output or secrets, and no Active
retries. **The repaired plugin was not reinstalled and retested with a live
provider** after the QUOTA error; a unit PASS is not a native retest.

No budget, side-effect, idempotency, trust-source, gate thresholds, model
backend semantics or retry authority were changed. Unsupported shell and
unidentified tool operations remain unsupported.

## 4. HTTP collector and evidence boundaries

`python3 scripts/phase8_2a_shadow_proxy.py --port 18783 --evidence <private-JSONL>`
forwards exact bytes to **a real, isolated** Laya/MLX Runtime on
`127.0.0.1:18782`. It accepts only the two Completion/Retry endpoints, only
loopback peers, and small bodies. It logs only the endpoint, salted hashed
request identity, status, decision, decision source, backend and duration.
It never logs task/result text, tool arguments, provider credentials, or raw
HTTP headers. The collector does not mock a model or native event.

- D-S2 issued **2 real Completion HTTP requests** through the installed
  adapter; both returned **503**, not a valid inference decision.
- One subsequent **direct manually invoked Retry HTTP smoke** (no Agent!)
  returned HTTP 200, `verify_state`, `decision_source=rule`, `backend=rule`.
  This confirms the forwarding path, **not** native Retry or Laya inference.
- Collector events were not securely bound to a specific native Turn by a
  shared verified request-ID trail; run-specific attribution is limited to
  isolation/timing. Do not represent cross-layer association as proven for DSH.
- The prior Hermes native Completion decisions explicitly recorded `mlx/model`
  in the real installed plugin state; that is the strongest available evidence
  of actual Laya inference for this experiment. The HTTP-only rule result
  must not be counted as Laya use.

`scripts/phase8_2a_verify.py --private-root <private-test-directory>` checks
bytewise artifacts, parses only DSH native JSON event *metadata*, rejects
orphan/duplicate IDs and missing Turn/Step boundaries, and summarizes only
allowlisted facts. It does **not** treat final text as success. Raw sessions,
provider usage and service ledger belong to the local Git-ignored private
folder, never a public release. Public summaries are **records, not
cryptographic execution attestations**. Unattributed collector events are
explicitly marked as such.

## 5. Noninterference, limits and omitted scenarios

- Hermes and DSH adapter modes were Shadow. Both native Agent file tools ran
  without a Gate-triggered stop/retry/model upgrade; H-S2 produced its artifact
  while Completion observations ran. D-S2's tool also executed despite
  Runtime HTTP failures. This is **narrowly observed fail-open behavior**, not
  statistically proven noninterference or a controlled OFF/healthy/down trio.
- **OFF vs healthy Shadow vs down Shadow** matched-provider comparisons:
  **not completed**. Provider rate limiting prevents more valid paired runs.
- Runtime unavailability was incidental when the isolated process command
  session expired, not a fully planned failure-injection matrix. Its HTTP 503
  evidence is retained, without claiming the full noninterference matrix.
- Multi-Turn, concurrent capacity, duplicate events, late results, a dropped
  write response, read-after-timeout, 429/403/validation faults and partial
  deliveries: **not natively completed**. Existing replay and bounded unit
  tests provide separate component evidence; no new production tolerance is
  implied.
- Hook callback time and inference/network latency have different meanings.
  In this sample, do not derive P95 or sum asynchronous inference into blocking
  latency. Native runs are too few to draw throughput or model-quality claims.

Reproducibility requires: matching pinned platform versions; isolated Hermes
profile with installed plugin; DSH headless patch with a real already-authorized
main-model provider; `completion_loop_probe_enabled=true` and
`retry_escalation_gate_enabled=true`; single-owner loopback Runtime and
collector; temporary test directory; strict provider/request/step/time caps;
and independent file and event verification. Formal verifier mode `scripts/phase8_2a_verify.py --private-root <path>
--formal-sha <frozen-40-hex-commit>` additionally rejects missing manifests,
wrong code versions, dirty trees and missing metric denominators. Existing
exploratory runs intentionally **cannot** satisfy formal mode.

The published scripts intentionally
**do not retrieve secrets** or auto-launch a paid provider. To repeat the real
scenarios, arrange authorization through a secure environment and consciously
invoke platform-native `hermes -z` / `dsh --profile headless` against private
configuration. Never put keys into shell arguments, committed patches, public
logs or a DSH_HOME shared with production.

## 6. Regressions, privacy and cleanup

At the development checkpoint, targeted Python tests:
**17 PASS** (`tests/test_retry_hermes.py` and
`tests/test_phase8_2a_evidence.py`). DSH `npm run typecheck`,
`npm run build`, `npm test`: **55 PASS**. Full Python regression: **857 PASS** on the final code candidate;
rerun after any changes. Public release/allowlist validation is performed
on the final candidate. These numbers are not historical Phase 8.1 passing totals.

Two owned short-lived local Runtime sessions and the loopback collector
were terminated or timed out, rather than continuing as permanent services.
Only the isolated profile was modified and its test plugin was disabled at cleanup;
installed production Hermes processes,
regular profiles, the stable DSH installation and the NAS main branch were not
restarted, reset or deployed. No public credentials, native raw session
contents or private filesystem paths are included in the export.

## 7. Independent acceptance matrix

| Field | Status | Reason |
|---|---|---|
| Hermes Native E2E | **PARTIAL** | Success + failed native tool observed; Retry failure path blocked by a now-fixed but untested native identity mismatch; no frozen post-fix provider rerun |
| DSH Native E2E | **PARTIAL** | Real success task, but no healthy linked Shadow result; failed-read path not run after provider QUOTA |
| Completion Observation | **PARTIAL** | Hermes native `mlx/model` observed; DSH only failure HTTP evidence, not valid inference response |
| Retry Observation | **PARTIAL** | Hermes native failure logged unsupported; native field bug repaired + regression tests, live retest absent; DSH failure not run |
| Shadow Noninterference | **BLOCKED** | No complete OFF / Shadow healthy / Shadow down paired native trials |
| Privacy & Cleanup | **PASS (scoped)** | Private raw records, allowlisted recorder, loopback-only test processes cleaned; requires final exit/port confirmation |
| Regression | **PASS (scoped)** | Targeted suites passed; full suite and public bundle audit to be completed |
| **Phase 8.2A Engineering** | **BLOCKED** | Two-platform four-chain and paired-failure/noninterference requirements unmet |
| Model Superiority | `NOT_EVALUATED` | Out of scope |
| Active Authority | `NOT_AUTHORIZED` | Shadow never made an execution decision |

**Next blocked prerequisite:** re-establish the previously authorized provider
quota/budget without switching or purchasing a second provider, keep the
repaired source pinned to an immutable commit, and rerun H-F1 + D-F1 followed
by D-S1 with healthy Runtime HTTP evidence; then run the small OFF/Shadow/down
and lifecycle comparisons. No automatic merge or production deployment is
authorized by this report.
