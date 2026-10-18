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
Only the isolated profile was modified and its test plugin was disabled at cleanup.
**Isolation qualification:** the native Hermes plugin install CLI printed
"Gateway reloaded plugins — active in the running gateway now: hooks".
This was a **hot hook reload automatically triggered by profile-specific
installation**, not a requested Gateway process restart. No production profile
was edited, but zero transient impact on the shared multiprofile gateway was
**not independently established** and is therefore not claimed. Regular
profiles, the stable DSH installation and the NAS main branch were not
reset or deployed. No public credentials, native raw session
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

## 8. Authorized StepFun Plan continuation (2026-10-18)

The user authorized **switching the main model to the already configured StepFun
Step Plan subscription**, specifically `stepfun/step-5-preview`. This **does not**
change the Laya/MLX decision model or grant Active control. Step Plan credentials
were read from an existing authorized source into test subprocess memory, never
written to source control or a shell command argument. The test used the
subscription endpoint under `/step_plan/v1`, **not** the pay-as-you-go `/v1`
endpoint. Plan-credit consumption is not independently priced or verified.

A fully separate, Git-ignored `HERMES_HOME` was created and the actual native
Hermes plugin was installed **pinned to the first exploratory PR revision**;
that home's CLI printed that a Gateway restart would be needed, but we did
**not** perform a Gateway restart or modify any production profile. DSH used
a separate native `DSH_HOME`, upstream pin `0.1.7-rc.2`, and a private
`llm-pi-ai` configuration routed to the real Step Plan provider. The pinned
DSH upstream did not natively register this provider, so this was a standard
provider extension, not a forged Agent event or main-model replacement.

All three actual native tasks below started on **clean, frozen source commit**
`fc49e69bd350aefd9626bb5975da2458569ee8aa` (the earlier two PR
commits plus a one-line local-private-home ignore). Later report-only changes
are not passed off as that same code SHA. The project-private launch script
and session traces remain Git-ignored. The remote Step Plan provider was
real, and an isolated request-cap forwarding service passed its HTTPS
requests through without creating model replies.

| Native task | Provider requests | Independent result | Completion Shadow | Retry Shadow | Verdict |
|---|---:|---|---|---|---|
| Hermes failed `read_file` | 2 main | Missing target remained missing; failed native event observed | Post-tool and turn-end reached real Laya/MLX | HTTP 200, `ask_user`, `rule`, unknown retry budget retained | **Previously blocked native Retry path now observed successfully** |
| Hermes `read_file`→`write_file` | 6 main + 1 auxiliary | **Exact output bytes match** | Post-tool and turn-end reached real Laya/MLX | Successful tools did not trigger Retry | Native chain works, **but violates the planned ≤3 main calls/task cap** |
| DSH failed native `read` | 3 upstream total, including at least 2 visible native steps | Typed `tool_call` + `tool_result.status=error` paired; missing target remained absent | Two HTTP 200 model/MLX observations | One HTTP 200, `ask_user`, `rule` | **Supported read-failure native path observed** |
| DSH normal write | 0 | Not attempted in this StepFun round | NOT VERIFIED | N/A | **BLOCKED by total request cap** |

The independent collector captured **8 successful** loopback Runtime requests:
**6 Completion Laya/MLX inference** and **2 Retry hard-rule resolutions**.
The Runtime metrics agree: `requests=8`, `backends={mlx:6, rule:2}`. This is
model execution evidence only for Completion, not for Retry: Retry correctly
selected a deterministic conservative path due to missing trustworthy budget.
No Agent execution was changed by those recommendations.

**Budget warning.** The Hermes failed read incurred 2 model calls. The Hermes
normal task incurred **6 main plus 1 auxiliary call**, even though the initial
per-task limit was 3; this overrun is explicitly not a PASS for budget
compliance. The DSH bounded provider-pass-through then forwarded 3 real
Step Plan requests. **Observed round total: 12/12** (including the Hermes
auxiliary). The explicit cap was reached. We stopped further Provider calls
rather than silently extending the budget or substituting fake responses.
The original experiment's 2-CNY monetary safeguard was not independently
priced in subscription credits, so **no zero-cost monetary claim** is made.

Sanitized evidence: [`results/processed/phase8_2a_stepfun_native_exploratory.json`](../results/processed/phase8_2a_stepfun_native_exploratory.json).
Evidence sources are kept separate: native Hermes plugin state; native DSH
Headless NDJSON tool/step/turn records; runtime forwarding logs; post-run
filesystem checks; and HTTPS forwarding request counters. The DSH HTTP
collector is scoped to an isolated single native run, but there is no
shared externally verified request-ID trail tying each DSH native call to
each specific Runtime decision. Do not infer more correlation than observed.

### Revised acceptance after the provider switch

- **Hermes native integration: PARTIAL.** Both tool success and tool failure
  now genuinely pass through the claimed observable shadow paths, including
  the fixed Retry field, but the success task exceeded its provider-call limit.
- **DSH native integration: PARTIAL.** Native read failure and Completion/Retry
  observations were reproduced with StepFun; the successful StepFun write
  and independent OFF/Shadow/Runtime-down comparisons remain outstanding.
- **Completion observation: PASS on observed tool/turn paths only**; no active
  stopping, incomplete/late-turn guarantees or quality claim.
- **Retry observation: PASS on the pinned failed-read path only**; other
  tool/side-effect outcomes remain unsupported or untested.
- **Shadow noninterference: BLOCKED** pending true paired OFF/healthy/down.
- **Phase 8.2A Engineering: BLOCKED**, Model Superiority: NOT_EVALUATED,
  Active Authority: NOT_AUTHORIZED.

Next native-provider phase must use a freshly declared finite call/credit
budget before the first new request, instrument the total Provider request
count across native and auxiliary flows, validate a DSH success task and
complete the controlled paired tests. Do not reuse the current 12/12 cap or
quietly treat an Agent's own retries as System One recoveries.

## 9. Bounded provider-proxy pilot and paired native noninterference (2026-10-18)

A follow-up pilot was run using **real StepFun Step Plan** `stepfun/step-5-preview`
and the existing Laya/MLX Runtime. Its new admission control is
[`scripts/phase8_2a_provider_cap.py`](../scripts/phase8_2a_provider_cap.py):
explicit `--execute-real-provider` opt-in, exact model/URL allowlist, atomic
cross-process request reservation before upstream I/O, **3 upstream requests
per run / 15 total**, with failed/retried/auxiliary requests included. A
reserved request is not refunded after timeout. Its private JSONL ledger
contains only run, slot, HTTP status and measured wall time; not prompts,
credentials, tool data or replies. The real Step Plan HTTPS responses are
forwarded, not simulated. Default CI does not invoke this provider.

[`scripts/phase8_2a_native_run.py`](../scripts/phase8_2a_native_run.py)
is an opt-in repeatable native single-task runner requiring an already
running cap proxy, a separate Hermes/DSH home, and a real environment-held
StepFun credential. For the revised read-only task, the file's nonce is
**not present in the Agent prompt**. An independent parser checks that a
native `read` tool's completed result, final Agent text and hidden original
file content agree. Files, full native events and logs are private and
Git-ignored; the published summary uses an explicit allowlist.

### Exact code/test scope

The initial DSH `write` exploration was on clean commit
`daf86c449e5ab20bfcbc4de8db5a60e0fafa4b25`: the Agent made one failed
`read` before a successful `write`, produced the correct output bytes, then
ended in `RATE_LIMIT` when the capped main-model request budget was exhausted.
The **business artifact succeeded but the Agent turn did not**. This run is
**not** counted as a successful native task.

The next three DSH native `read` trials and the Hermes degraded native `read`
trial all ran from a separate clean frozen commit:
`5e47348a042daaddf227a8849002e15d133bca32`. Each was invoked under
an explicit three-provider-request hard cap, a 90-second wall timeout and
an isolated process/home. They used *identical task semantics* with distinct
private input paths. Read content verification used the actual native DSH
tool-result payload; the Agent's final answer was never the sole oracle.

| Platform / mode | Independent original-task result | Native status | Provider requests | Gate HTTP |
|---|---|---|---:|---|
| DSH OFF | input unchanged; read result + final nonce match | turn completed, 1 paired read | 3 | **none** |
| DSH Shadow / healthy Laya | same | turn completed, 1 paired read | 3 | Completion **200, 200**; both `mlx/model` |
| DSH Shadow / Runtime down | same | turn completed, 1 paired read | 3 | Completion **503, 503**; native turn unaffected |
| Hermes Shadow / Runtime down | input unchanged; final nonce matches | native task completed; Completion hook probe and turn-end each observed | 3 | Completion **503, 503** |

Native DSH OFF/Shadow/down elapsed seconds: **8.997 / 9.634 / 9.231**,
respectively, each **n=1**. These are *descriptive run observations*;
there is no P95 and they cannot prove zero overhead or statistically equal
model behavior. The inspected Shadow adapter paths do not apply Completion or
Retry advice to native requests, tools, termination, authorization or model
selection; no Active authority was granted. The HTTP collector's privacy-safe
run-time windows support association in this isolated sequential test, but
shared turn-level correlation through both native and Runtime request IDs was
not proven.

The durable ledger accounts for **15/15 forwarded HTTPS Step Plan requests**, all
15 receiving HTTP 200 from the upstream endpoint: three in the initial
unsuccessful write attempt, then three for each of the four completed native
read tasks. It is a new finite round, separate from the earlier 12-request
StepFun exploratory budget. Provider credit/monetary spend remains unknown.
No sixteenth upstream request was forwarded, no change of paid Provider was
made, and model suggestions never induced native retries.

Independent adjudication is in
[`results/processed/phase8_2a_stepfun_shadow_paired_read.json`](../results/processed/phase8_2a_stepfun_shadow_paired_read.json),
generated by the [paired verifier](../scripts/phase8_2a_paired_verify.py).
The scoped finding is **DSH Native OFF vs healthy Shadow vs Runtime down:
PASS for this single read-only task family**, supplemented by a separate
Hermes degraded-native run. This is **not** a blanket, multi-tool/multi-session
noninterference or performance claim.

### Lifecycle hardening discovered during offline closeout

After the real runs, inspection found that the DSH Retry observer's cleaned
per-turn counters could be recreated by late `tool/result` events lacking an
active native turn-start marker. A narrowly scoped DSH guard was added:
Retry now requires an active native `turn/start` identity, has bounded live
turns, and discards late failed tool events after `turn/end`/`session/end`
without resurrecting the counter. This fixes an **offline-verified lifecycle
bug** with a new regression and retains Shadow behavior. Its *post-run source
commit is different*, so the provider-backed DSH evidence above does **not**
constitute a native E2E retest of this lifecycle change. In particular,
real multi-Turn same-session, many simultaneous native sessions and late
worker completions remain **NOT NATIVE-MEASURED**.

### Acceptance after this second round

- Hermes native success/failure observed across the existing bounded pilots.
  A separate degraded run confirms native fail-open; full matched
  OFF/healthy/down Hermes *same-task* trio was not repeated.
- DSH native success/failure observed; DSH single-read OFF/healthy/down
  **passes within stated scope** on frozen pre-lifecycle-fix code.
- Completion/Retry supported native tool observations: **measured**; actual
  Laya inference was observed only on model-path Completion requests; unknown
  budgets correctly fall back to Retry rules.
- Privacy, per-run/network capacity control and cleanup: **PASS in tested
  scope**; long-running production capacity/energy implications are unknown.
- Multi-turn/concurrent native lifecycle & the late-event fix on final
  source commit: **not yet provider-backed revalidated**. No threshold,
  model superiority or Active Readiness tests were performed.
- **Phase 8.2A Engineering: BLOCKED** until the final lifecycle hardening and
  broader declared native coverage are verified on a frozen final candidate.
  Model Superiority: NOT_EVALUATED; Active Authority: NOT_AUTHORIZED.

## 10. Final offline regression and publication boundary

The final source candidate adds a bounded, **explicitly real-provider-only**
StepFun pass-through request limiter, a minimal repeatable native-run entry,
independent paired-native evidence checks, and a narrowly scoped DSH
late-result lifecycle guard. The real provider trials did **not** execute
this last guard revision; that distinction is maintained in Section 9.

- Python: **866/866 tests passed**, including cap enforcement under concurrent
  incoming requests, malformed/unexpected model rejection, both per-run/global
  limits, request failures that still consume slots, strict DSH native event
  pairing, and post-run independent verifier checks.
- DSH: TypeScript typecheck and build passed; **56/56 tests passed**, including
  a late `tool/call` and `tool/result` after `turn/end`/`session/end` that must
  not create fresh Retry state or extra Runtime requests.
- Model quality and noninterference timing significance remain
  **NOT_EVALUATED**. The original StepFun task cap was enforced in real
  network traffic, not merely tallied after the fact.
- The committed report and processed JSON are sanitized *derived evidence*.
  The native full task, original file nonce, token, provider headers and
  unredacted Agent outputs stay in the restricted Git-ignored test workdir.
  SHA and field consistency make records auditable, **not** cryptographic
  proof of an entire execution.
- Final source has **not** received a new provider-backed run after the DSH
  late-event fix because this round's **15/15** provider request quota is
  exhausted. A new explicit provider budget and frozen-code rerun are
  required before calling the *latest* candidate an engineering acceptance.

Final classification (scoped real tests and latest offline validation kept
separate):

| Check | Judgment |
|---|---|
| Hermes Native E2E | PARTIAL: real success/failure and degraded Shadow, no latest-SHA full trio |
| DSH Native E2E | PARTIAL: native failed read and successful read; lifecycle fix not re-tested native |
| Completion Observation | PASS **only for observed tool-result/turn-end model paths** |
| Retry Observation | PASS **only for supported failed-read rule paths** |
| Shadow Noninterference | PASS **only for DSH isolated one-Turn read OFF/healthy/down trio** |
| Privacy & Cleanup | PASS in isolated scope; no production writes / private trace export |
| Regression | PASS: 866 Python + 56 DSH; typecheck/build clean |
| **Phase 8.2A Engineering** | **BLOCKED**: missing native revalidation of final DSH lifecycle patch and wider real lifecycle matrix |
| Model Superiority | NOT_EVALUATED |
| Active Authority | NOT_AUTHORIZED |

No production Canary rights, automatic retry, active stop, model ranking,
JEV calls, stable install updates, or automatic PR merge were authorized.
