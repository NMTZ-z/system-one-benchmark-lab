# Phase 8.3A — Native StepFun + Laya Shadow real-provider attempt

**Historical first-attempt verdict (early 2026-10-21): BLOCKED BEFORE
PROVIDER EXECUTION. Current late-2026-10-21 result: H1/H2/H3 real
native tasks each executed once; H2 healthy Laya Shadow and H3
Runtime-down fail-open passed scoped criteria. Overall Phase 8.3A
remains BLOCKED by one historical H1 unresolved Provider request.**
**Execution environment: isolated Phase 8.3 worktree.**

This document is an APPEND-ONLY CHRONOLOGY. Its early sections describe
the first blocked authentication attempt, not the current latest
experiment. See Sections 12–16 and the separate H1/H2/H3 real
reports for what ran later. Do not substitute old Phase 8.2A native
data, Phase 8.2B Mock evidence, or Phase 8.3 synthetic accuracy for
the independently observed new real-provider tasks.

## 1. Established baselines

- GitHub main: 062d52e753e7e00d91a536dc81e9d85b8819cb12.
- Phase 8.3 Draft PR #9; dedicated clean feature worktree, unchanged
  production and NAS main.
- Predeclared test protocol source commit before any external request:
  5dfc5b6add32eeb37bd8a8488485f77d529e4758.
- Existing StepFun Step Plan test-profile read-only authentication status
  reported logged in. This is only an **auth metadata observation**:
  not proof of request routing, spend, credit balance or successful
  current main-model inference.
- No existing production Gateway, Agent Home or unrelated loopback Runtime
  was reconfigured, restarted or altered.
- The private test environment for this experiment **was not created**:
  an attempted operation to connect existing isolated credentials to a
  fresh isolated native test setup was rejected by the available tool's
  external safety check. The operation did not execute; a subsequent
  read-only file check confirmed the new Phase 8.3 private test directory
  did not exist.

## 2. What was not done

The tool safety block was respected. We did **not** retry credential
access using an alternate route, link/copy any token, inspect or print a
secret, move to production authentication, use a secondary Provider, or
bypass the capped egress plan.

No Phase 8.3 native tool tasks were launched. No StepFun Step Plan proxy
listener, new provider budget ledger, private Session stream or fresh
native event / HTTP trace was created. Therefore there is **no measured
Provider attempt denominator** for new native sessions. The observed
number of *new experiment initiated requests* is 0, but this is
**not a statement about the user's total subscription usage**.

Per-scenario status, all **BLOCKED / NOT RUN**:

| Test | Native platform | Test state | Real native evidence |
|---|---|---|---|
| H1 | Hermes OFF read | NOT RUN | none |
| H2 | Hermes Shadow healthy | NOT RUN | none |
| H3 | Hermes Shadow Runtime down | NOT RUN | none |
| H4 | Hermes Shadow failed read | NOT RUN | none |
| D1 | DSH SDK OFF read | NOT RUN | none |
| D2 | DSH SDK Shadow healthy | NOT RUN | none |
| D3 | DSH SDK Shadow Runtime down | NOT RUN | none |
| D4 | DSH SDK Shadow failed read | NOT RUN | none |

**Do not claim 8.2B exact native-to-HTTP correlation on a fresh real StepFun
execution, real Provider token spend, real Agent overhead or savings.**

## 3. Evidence obtained without credentials

Existing bounded test components were reviewed and reused without
reimplementation:
- Phase 8.2A atomic Provider reservation and request ledger, including
  proper fail-closed behavior for exhausted/corrupted budgets.
- Phase 8.2B independent HMAC native/Adapter/HTTP correlation validator,
  including no PASS from clock proximity alone.
- Phase 8.2B metadata-only Evidence Contract and offline synthetic verifier.
- Phase 8.3 preregistered Shadow matrix and previous new synthetic holdout.

The supplemental offline regression under
tests/test_phase8_3_native_real_budget_preflight.py checks 8 runs ×
3 physical request slots = 24 maximum across one durable ledger,
nonrefundable failed/unknown requests, corruption refusal, missing
native event provenance, and lack of false task PASS when no Agent ran.
These are **unit/contract tests, NOT real main-model calls or native E2E**.

## 4. Scope of next permissible action

Real tests remain **BLOCKED** until the owner/environment establishes a
supported, independently authorized and bounded isolated authentication
path that passes the tool safety boundary. Do not resolve the block by
linking/copying old credentials, reading a production secret or routing
around permission checks.

When properly available, retain the frozen test plan:
only the existing StepFun Plan endpoint, total physical cap 24,
per-run cap 3 and <=90 s per native task, real Laya/MLX Shadow,
independent native file oracle, HMAC exact correlation, no Active.
Stop and separately report any unmatched native results or
Provider count, unknown usage or budget mismatch.

**Final offline verification (2026-10-21):**
Python test suite **1012/1012 PASS**; DSH Vitest **64/64 PASS**,
TypeScript typecheck **PASS**, TypeScript build **PASS**. The focused
new/legacy provider budget and 8.2B causal-correlation regression
completed **28/28 PASS**. No paid Provider calls were made by these
offline tests; their Mock HTTP servers were loopback-only.

**Engineering offline evidence:** PASS within non-Provider scope.
**Native Real Provider Validation:** BLOCKED.
**Model incremental real-Agent value:** NOT_ESTABLISHED.
**Actual savings:** NOT_MEASURED.
**Active readiness:** NOT_AUTHORIZED.


## 5. Clean empty profiles and offline SDK initialization (2026-10-21)

Following the previous safety block on legacy credential linkage, we
created a NEW Hermes OFF-only test profile and two DSH OFF/Shadow SDK
configurations using scripts/phase8_3_prepare_clean_home.py. Only safe
source-controlled plugin bytes and explicit loopback test settings were
written; no legacy/production auth file, key or token was copied or linked.

With zero credential environment variables and no Agent task submitted,
the official native DSH SDK completed initialize and shutdown in both
OFF and Shadow modes, with process exit code 0. The repeatable
scripts/phase8_3_sdk_offline_preflight.py reproduces this no-Provider
test and outputs only allowlisted status fields.

The Hermes test home remains credential-empty and in OFF mode, so
real StepFun Provider requests and native Agent task acceptance remain
BLOCKED. The earlier credential restriction was not bypassed.

See the official operator handoff PHASE8_3_OFFICIAL_AUTH_HANDOFF.md
for the separate, supported interactive authentication path.


## 6. Credential-stage exact check and regression (2026-10-21)

The fresh Hermes OFF Home and DSH OFF/Shadow SDK patches were audited again.
The strict official auth preflight uses an **allowlisted clean environment**
that drops inherited STEPFUN/other Provider tokens, route overrides and
production HOME fallbacks. It returned MISSING_NEW_PROFILE_LOGIN, with
credential_stage_ready false and live_provider_budget_attested false.
The new test auth.json still does not exist.

Both DSH SDK modes requalified cleanly with no key in the subprocess
environment, initialize/shutdown only. No provider call, Session prompt
or native tool action occurred.

Python 1030/1030 PASS, DSH Vitest 64/64 PASS, TypeScript typecheck and
build PASS. New symlink, mode, route, inherited-token and byte-identity
regressions pass.

**Native Real Provider E2E is still BLOCKED.** The only supported next
step is for the owner to use the official fresh test-home interactive
auth login described in PHASE8_3_OFFICIAL_AUTH_HANDOFF.md. The prior
tool safety block has not been bypassed.

## 7. Test Home dependency repair diagnosis and supported recovery (2026-10-21)

The new Hermes auth-add request failed **before any credential input**,
reporting a missing committed dependency environment for its external
repository-private HERMES_HOME. This was confirmed in Hermes PM source:
the project's dependency state is scoped to a data Home, so the test
Home did not inherit ~/.hermes/installs.

An explicit repair attempt under the **test Home only** was stopped at a
bounded timeout after beginning uv dependency installation. No dependency
generation or token was committed there; the partial test-only
install/cache/repair marker were cleaned up without touching the owner
installed dependency facts. No real Provider call was made.

A separate credential-empty data Home at ~/.hermes/system-one-phase83lab,
outside the automatic Hermes profiles/ area but inside the existing
shared dependency root, was prepared with public plugin files and
OFF-only test settings. A real official Hermes auth status call under
this new Home returns **stepfun: logged out**, not the former dependency
error. No old credentials were copied or linked, and no Provider traffic
was initiated.

The official user-controlled login and independent safe status preflight
are documented in PHASE8_3_OFFICIAL_AUTH_HANDOFF.md. The eight actual
native tasks remain **NOT RUN**. No completion, retry safety, Provider
cost or Agent savings claims are created from this configuration fix.


## 8. Exact test-only native-run path (no Provider executed)

The legacy Phase 8.2A native-run CLI originally accepted only Hermes
Homes beneath repository-private, so it would have rejected the new
supported shared-dependency Home after successful official login.
A narrow Phase 8.3 exception now accepts only the fixed
~/.hermes/system-one-phase83lab Home after its independent secure
source/auth and Provider-route checks. The runner still requires the
frozen clean SHA, shadow-only mode, the pre-network budget proxy,
read-only native tasks, at most 24 global physical StepFun attempts,
3 per task and 90-second task timeout. All other Homes retain the old
strict rule.

No real Provider request was launched by this adjustment. Any native
SDK/Agent success and fresh HMAC causal correlation remain BLOCKED
until a fresh official auth token is provided by the owner, live
budget egress is verified and the scenario-specific evidence oracle
is ready.


## 9. Shared-dependency bootstrap completion and new-run safeguards

After diagnosing the broken repository-private Hermes PM environment,
the new safe data Home was prepared under ~/.hermes/system-one-phase83lab.
The official Hermes CLI now starts and returns a normal logged-out
StepFun state. It has a separate empty .env and fresh public plugin
copy with OFF-only settings and loopback-only main Provider URL.
No old Provider token or production config was imported.

The existing native runner now accepts only this exact test Home,
after independent official-auth readiness and byte/endpoint checks.
It rejects non-read-only tasks, other Provider ports, broader than
24 global or three per-case physical requests, runtimes exceeding
90 seconds, and Active/Canary mode. The previous strict HOME rule
for all other locations remains in effect.

Final regression **1051 Python PASS** and **64 DSH Vitest PASS**,
TypeScript typecheck/build PASS. Real eight-case Provider-backed
validation is still **BLOCKED: the new Home has not yet been logged in**.
The existing planned test cap is not consumed by any of these checks.

## 10. Post-login physical Provider route hardening (2026-10-21)

The owner completed login in the fresh isolated Hermes Home. The first
read-only verification returned UNVERIFIED_PROXY_ROUTE because Hermes had
an environment-seeded StepFun record and a separately added manual one.
The official Hermes auth remove command was executed against the
**test Home only** to suppress the unused environment record. The new
manual credential was retained unchanged. No Provider request occurred.

Source inspection found that Hermes' runtime credential rotation can
use the credential's persisted URL. Merely validating config.yaml's
loopback Provider URL does not prove an actual request cannot bypass
the cap. A stronger Phase 8.3 preflight now requires exactly one manually
authorized StepFun pool row, with its OWN stored URL pointing at the
audited local budget proxy. Any other pool entry or external URL blocks
a native Provider attempt.

An isolated-only atomic metadata updater was added to change ONLY the
new test manual credential's base_url from Hermes' canonical Step Plan
registry endpoint to the local proxy. It preserves the existing key
in the same protected file, prints no key and never accesses another
Home. The original test-only budget and read-only Agent task limits
remain in force. Real Native E2E must still be separately executed and
correlated; login readiness does not prove an Agent outcome or savings.


## 11. Frozen H1 real Provider native task preparation

A single-shot H1 native test runner now exists at
scripts/phase8_3_real_hermes_pilot.py. It starts the existing Step
Plan pass-through with the previously authorized 24 global and 3
physical requests per run, then invokes the native Hermes OFF-mode
read-only task. It uses the newly pinned isolated manual credential
and does not load the owner's default Home or alternate Provider.
All raw provider, native and file evidence is confined to ignored
test storage. It refuses a dirty candidate, inconsistent auth route,
a preexisting ledger, wrong test mode, occupied proxy port, or
unbounded outbound cap.

The independently extracted Hermes SQLite tool call/result and
original-file oracle are checked separately from the Agent's final
text. A task that fails its strict proof is reported PARTIAL/BLOCKED,
never converted to a successful Agent result. The runner is opt-in
and never reruns H1 by overwriting prior evidence.

This section only describes a prepared test harness. Real execution
must be reported in a subsequent separate, truthfully pinned
post-execution record, not inferred from preflight.

## 12. Executed real StepFun H1 OFF test: task PASS; budget BLOCKED

A single one-shot H1 was performed on clean, pinned
Git 82993477667817c8941caa429feea576d091a424 with the newly
authenticated and loopback-pinned Hermes test Home. Real upstream
StepFun Step Plan was used behind the explicit 24-global/3-run
pre-network reservation cap. No other real case was executed.

The native Agent returned successfully and an independent SQLite,
tool-result and original-file oracle verified the read_file task.
However, 3 real HTTPS requests were attempted while the private
proxy ledger contains terminal records for only two HTTP 200
responses. Slot 1 remains attempted/unresolved. The real proxy was
stopped immediately at Agent completion under the original frozen
harness, potentially truncating the pending request. No retrospective
Provider outcome or fee can be inferred.

The independent budget reconciler reports BLOCKED
(reserved_without_proxy_result), 1 physically unattributed
request and unknown billing. H1 task-only PASS is not Phase 8.3A
overall PASS. New real StepFun tasks are STOPPED until safety
qualification of the outstanding lifecycle and test harness. A
bounded no-new-request drain has been added after the fact, with
offline-only tests; it does not change past evidence.

Full facts and limitations:
PHASE8_3_REAL_NATIVE_H1_REPORT.md.

## 13. Post-H1 independent verification and test stop

H1 was independently re-adjudicated using the original isolated Hermes
SQLite session/tool records, original hidden file bytes, the separate
durable StepFun provider ledger and the original native-run summary.
The fixed execution commit is 82993477667817c8941caa429feea576d091a424.

Task result is PASS_SCOPED. Provider budget integrity is BLOCKED with
one attempted/unfinalized slot and one physically unattributed request.
No further Agent native scenario was run and no Provider attempt was
retried or retroactively marked complete.

The revised harness waits for already attempted Provider responses to
finish before stopping its proxy, subject to a bounded upper limit; it
does not generate new provider calls. Full Python regression
1082/1082 and DSH 64/64 passed, alongside TypeScript checks/build.
This is offline code validation of the mitigation, not proof the old
unknown Provider outcome was resolved.

See Phase8.3 real H1 report and the processed H1 aggregate for the
exact separated task/transport evidence boundary.

## 14. H2 separate preregistration and local transport requalification

The H2 Shadow-only preregistered protocol is published as
PHASE8_3_H2_PRERUN_PROTOCOL.md, frozen before any real H2 request.
It preserves the original H1 private Provider ledger and all three
H1 physical reservations, including one unfinalized slot, when
reserving any new H2 physical traffic. No prior request is refunded.

Seven deterministic local HTTP fault-injection cases now cover
delayed Provider completion after Agent disconnect, explicit
unknown upstream outcome, historical ledger tampering, duplicate
or undeclared run identity and shared physical budget caps.
Separately, a REAL LOCAL Laya/MLX-only service returned two
HTTP 200 Completion decisions, with key-based request/response
identity matching, without a StepFun main Provider request.
These are engineering preflight evidence, NOT native real-Agent H2.


## 15. H2 offline preregistration regression

A new scoped H2 Shadow-only runner and a shared H1/H2 physical
Provider-ledger reader have been implemented without changing the
original H1 record. Historical H1 data is checksum-pinned, and each
new H2 request must remain within the same 24-global / 3-per-run
reservation ledger. HTTP drain is limited to H2 while the unresolved
H1 slot remains permanently unknown and Phase 8.3A overall stays
BLOCKED until that historical limitation is separately adjudicated.

Local-only delayed/disconnected Provider integration and concurrent
ledger append/read tests passed. The real local Laya/MLX Runtime and
HMAC observer each returned 2 completed Completion model decisions,
without any main StepFun request.

Full preflight Python 1102/1102 PASS, DSH 64/64 PASS, TS typecheck/build
PASS. **No H2 real main-provider execution has occurred yet**.
Read the separately frozen H2 pre-run protocol for acceptance limits.

## 16. Actual StepFun H2 Shadow E2E: scoped native/correlation PASS

The H2 predeclared real Provider execution occurred exactly once
on clean SHA 0dc626ff86038702f74027b4a988d21f096f72d9.
Hermes executed a genuine native read_file and the separate
private-file/native SQLite oracle passed. The isolated Runtime
used actual Laya/MLX for two Completion model decisions; all
two originating Agent event/Adapter/HTTP links were independently
HMAC verified with echoed request IDs (2/2, HTTP 200).

The durable Provider cap was not reset. H1 retained three original
physical requests, including one unknown outcome; H2 reserved
physical slots 4-6 and all three reached real StepFun HTTP 200
with full lifecycle completion. No new unknown H2 outcome.
H2's own budget-integrity accounting is still PARTIAL on
logical attribution (three physical vs two native reported
main-model calls) and absent Provider billing evidence.
The overall Phase 8.3A budget history stays BLOCKED on H1,
notwithstanding valid scoped H2 observations.

Test Home was returned to OFF and all isolated test services
were stopped. H3/H4 and all DSH real tasks remain unrun,
as do any active policy tests. See the new
PHASE8_3_REAL_NATIVE_H2_REPORT.md and independently
adjudicated machine-readable H2 summary.


## 17. Post-H2 honest budget scope and regression

The newly independent private-to-public H2 adjudicator verified all
original native read proof, real local MLX event identities and
StepFun HTTP ledger outcomes. H2 has no unfinalized physical calls;
its Provider cost attribution is still PARTIAL. The older H1
missing terminal record remains unchanged and prohibits promotion
of the overall Phase 8.3A Provider history to PASS.

Post-H2 1121 Python tests passed, DSH Vitest 64 passed and
TypeScript typecheck/build passed. No extra StepFun calls or
production modifications followed the single H2 pilot.

## 14. Pre-H3 title-generation hypothesis and historical evidence

Source inspection of Hermes v0.22.1 confirms background
title_generation runs an asynchronous model call for a new session
by default. The original test Home did not override title generation.
H2's first physical Provider request lasted 33.13 seconds, outliving
its 29.581-second Agent execution. The oneshot process waits at
most 10 seconds for a background title thread and may exit before
it finishes. Auxiliary API counts in H1/H2 were recorded as zero.
This is a leading explanation for the third physical request and
the original H1 incomplete first request, but not a proven per-slot
attribution, since proxy records did not retain request purpose.

For the separately frozen H3 Runtime-down test, only the isolated
test Home's model-generated title upgrade is disabled, while ordinary
deterministic titles stay enabled. This permits an observational
physical-to-logical count check under an independently documented
configuration change. Prior real H1/H2 evidence is not modified
or relabeled, and the original 24 physical request budget remains.

H3 pre-model source and experiment contract are described in
PHASE8_3_REAL_H3_PREREGISTRATION.md.

## 15. Actual H3 real native fail-open execution and post-run adjudication

One explicitly authorized H3 real StepFun Step Plan task ran on the
clean preregistered 40a7b4416db07e6eedcf505131e0c9b3e1a98eac
source. The isolated Hermes Agent's read_file task completed
correctly; independent native SQLite and original file evidence
matched, and the final answer was supported. Runtime port 18782
was **intentionally DOWN**. The isolated observer recorded two
real HTTP 503 and native Completion hooks recorded two failed_open
events, with independent **2/2 keyed native/Adapter/HTTP correlation**.
No action authority was granted to System One.

H3 added physical slots 7–8 to the same append-only 24-slot
Provider budget; both were attempted and terminal HTTP 200.
For H3 only, background model-generated session titles were
disabled in the test Home. The resulting **two physical Provider
requests vs two native-reported main calls** support the hypothesis
that background title generation caused H1/H2's extra requests,
but the original physical requests were NOT labeled by role and
cannot be conclusively assigned. The original H1 slot 1 remains
attempted and unresolved.

The H3 one-shot run finished with scoped PASS and was not retried.
The isolated test Home was returned to OFF and no test-only
listeners remained. H4 and DSH real tasks remain NOT RUN.
Phase8.3A overall is still BLOCKED on historical H1 physical
request terminal integrity and unmeasured Provider billing; no
Canary/Active or new paid task is approved.

The independent real-H3 verifier and allowlisted public aggregate
were added after the original frozen real-run source. See
[H3 native fail-open report](PHASE8_3_REAL_NATIVE_H3_REPORT.md).

### Post-H3 verification and independently preserved historical H1/H2/H3

After the H3 original read-only task and failure-control observations,
a separate post-run verification exposed an earlier replay limitation:
H1 used to parse the entire growing global Provider ledger and H2
used to collect ALL stored plugin observations, including later H3.
They now respectively use the SHA-256 authenticated H1 original
first-ten-row archive and only the exact original H2 HMAC request
refs. H3 uses its own archived keyed references, native file
oracle and first-30-row Provider snapshot.

All three historical cases revalidate with the ORIGINAL decisions,
without a new main-model request: H1 remains
BLOCKED_BUDGET_RECONCILIATION (1 unknown physical request), H2
PASS_SCOPED, H3 PASS_SCOPED. New tamper tests refuse mutated,
duplicated, missing or cross-run evidence.

Final full regression: Python 1151/1151 PASS, DSH Vitest 64/64
PASS, TypeScript typecheck and build PASS. H4 and DSH
D1–D4 real Provider tasks remain NOT RUN.

## 16. H4 failure-tool and DSH native evidence OFFLINE prequalification

After the genuinely executed H3 fail-open task, the next phase
focused on zero-provider hardening, not paid H4/DSH tests. Hermes'
installed native read_file returned structured not_found and error
for a purposely absent ignored private file, without generating
or modifying the target. Its actual post-tool observer classifier
returned status=error/error_type=tool_error. An H4-only test
scenario now records a private original missing-file target before
the future Agent runs and requires exactly one paired native
read_file failure, not final-model self-report. Actual Retry Shadow
observation is NOT YET ESTABLISHED by this unit-level evidence.

The original global 8 StepFun reservations were verified byte-for-byte
against the H1+H2+H3 published ledger digest. Future H4 is limited
to append-only slots 9–11 within the old 24-global/3-case cap.
Nothing was written to H1/H2/H3 historical results.

DSH has a separate strict OFF/Shadow SDK patch and in-memory
credential-environment contract that explicitly avoids copying
the new Hermes Home's key. Native DSH session.event tool identities
and typed isError are validated against synthetic success/failure
fixtures. Actual DSH secure operator credential input and
Provider-backed native run remain BLOCKED/NOT RUN.

The distinction between H4 standalone typed tool-failure proof,
true Agent native failure/advisory proof, independent native-to-HTTP
correlation, Provider usage attribution and Active readiness is
documented in PHASE8_3_H4_DSH_OFFLINE_QUALIFICATION.md.

### H4/DSH no-Provider QA completion (2026-10-22)

The H4 read-missing independent negative tool oracle and DSH native
SDK credential/evidence checks passed the completed full regression:
Python 1201/1201, DSH Vitest 64/64, TypeScript typecheck and build
PASS. The Hermes file-tool failure and typed error derivation tests
made zero StepFun model calls, and DSH read-only SDK checks used no
credential. Actual H4/D1–D4 Provider-backed tasks remain NOT RUN.
The physical global Provider ledger remains at 8/24 attempts with
H1's original unknown still unchanged.

## 17. H4 one-shot blocked by host Gateway before Provider (2026-10-22)

The H4 one-shot candidate was frozen as a32eb078593cb4a9139c9aa181d017b9bb010298
and test Home set to Shadow. It started only isolated localhost
Laya/MLX and observation/proxy processes; when the native Hermes
-z CLI started, the current host-wide Gateway was already serving
other profiles, and did not serve the standalone System One test
Home. Hermes refused the additional Gateway startup before
any native Session/file tool or main Provider request.

Original private H4 child evidence records process_exit_code=1,
an empty stdout/no usage, an unchanged absent-file target,
zero actual native SQLite sessions and **0** physical H4
reservations/attempts; the cumulative original Provider digest
is unchanged from H3, still 8/24 with one H1 unknown.
The outer test restored OFF and stopped all test-only listeners.

A real safety bug was identified in the native child wrapper,
which printed the true process_exit_code=1 but itself returned
Unix exit 0. A later commit now treats any nonzero/missing/timeout
native child as a failed wrapper. This corrected code was NOT
the frozen H4 candidate and does not upgrade or overwrite the
original incomplete H4 evidence.

The installed official Hermes native in-process run_oneshot
still constructs AIAgent directly, without a Gateway connection
in that source path. It was inspected ONLY in a clean environment,
no native task or StepFun request launched. H4 is NOT rerun.
Any future direct-entry real experiment must be preregistered
separately, never overwrite this H4 private original.

See PHASE8_3_H4_GATEWAY_ADMISSION_INCIDENT.md and the read-only
aggregator. Global real H4 E2E is BLOCKED_BEFORE_NATIVE_AGENT,
not a real Retry Shadow failure result.

## 18. H4B reversible direct-native Agent source and zero-provider rehearsal

Following the original H4 Gateway startup refusal, a DISTINCT
H4B preregistration fixes the native route by choosing Hermes'
official process-local run_oneshot/AIAgent entry. To meet the
owner's requirement that local work be reversible, the new
child runs under a macOS Seatbelt sandbox with only one exact
read_file tool, one private absent target, no production
file writes, and only local 18793/18794 network outlets.
The current test Home must be OFF before a durable SQLite,
plugin state/source and config snapshot is written. Its
credential bytes are never backed up by test helpers;
the source itself is run with a separately user-authorized
credential bound to the physical-cap proxy.

A disposable stronger-than-real Seatbelt rehearsal imported
official run_oneshot and the single-read toolset with zero
network and zero Agent/Provider requests, leaving all
nonproduction Home state digests intact. Further offline
tests cover WAL SQLite recovery, temporary plugin-file cleanup,
process group PID-reuse denial and strict native Retry HMAC
joining. The real H4B original run directory and recovery
checkpoint were NOT created during this source preparation.

The original H1/H2/H3 cumulative StepFun ledger still has
exactly 8 attempts (7 HTTP 200 and original H1 1 UNKNOWN);
the original H4 Gateway-block attempt has 0. H4B new
real Provider-backed native qualification remains subject
to an exact clean frozen SHA and a separate one-shot run.
No historical record is retroactively altered or consumed.

## 19. H4B one-shot Seatbelt admission blocked by /dev/null, rollback verified

The first distinct H4B real-native-source experiment was frozen
at 633c914fe9b78b7515cfcfbe4795f5d2dbd3aadf.
The enforced macOS sandbox denied the official Hermes
run_oneshot's open(os.devnull, "w") before creating AIAgent.
The underlying one-shot returned exit 1, with zero native
SQLite Session/tool records, zero real StepFun requests,
zero Completion/Retry Gate HTTP events. This does not
answer the intended H4B native tool-failure/Retry question.

ALL 4 original H4B-owned process groups were verified
stopped by owner PID/PGID/start-time metadata. The
test Home original SQLite/plugin state/source/config
and OFF mode were restored using the pre-run private
checkpoint; test auth metadata unchanged. No original
H4B attempt or recovery proof was overwritten or
retried, and no user production Gateway/Agent was touched.

A POSTRUN source revision permits only the system /dev/null
output sink, while still denying all production files,
all external network and non-H4B tool access.
A strict all-network-denied offline rehearsal then
successfully called the real Hermes one-shot preamble
with synthetic _run_agent replacing the actual model
call; original test Home read-only digests matched.
No Provider expenditure occurred.

The original shared StepFun ledger remains 8 physical
attempts; H1 slot 1 unknown and Phase8.3A global
integrity remain BLOCKED. H4C (if later considered)
must be a new pre-registered case, never an
automatic retry of H4B.

## 20. Pre-H4C independent case and reversible preparation

A new H4C failure read case was prepared with a distinct
h4c_missing_read ID and h4c_recovery. H4B historical private
recovery, Session/Retry observations, typed file target, OS
Seatbelt logs and production Gateway remain untouched.
Same native AIAgent model and Laya Shadow scope, but isolated
ancillary local services' HOME/cache now point only within
the H4C disposable run folder. The H4C zero-network startup
rehearsal passed without running a real Agent or StepFun.
Native tool failure and Retry Shadow still require separate
real H4C evidence. Original physical Provider ledger is
unchanged at 8 attempts; no prior UNKNOWN request is rewritten.

## 21. Original H4C native startup blocked, full rollback verified

H4C was a separate one-shot native case, not a replay of H4B.
After 1338 Python / 64 DSH prereg tests and source
SHA 8776de71a88821dffd84bfd4976927fd0cfe9c3a
was frozen, its true Hermes in-process run_one_shot
returned SystemExit(1) inside _run_agent before a
native SQLite Session or actual read_file call was
persisted. Exact initiating subsystem UNKNOWN because
the official one-shot suppresses traceback internally.
No local Completion/Retry observations were recorded
and the StepFun physical budget proxy recorded ZERO
new H4C requests.

All four new test-only process groups stopped and
H4C-only online SQLite snapshot restored original
test Home state/config/plugin and OFF. Test credential
metadata unchanged, H4B original rollback and production
Gateway not modified. Cumulative Provider ledger still
8/24 physical attempts, 7 HTTP 200 and one original
H1 UNKNOWN. No paid retries, no Active or Canary.

H4C independent incident and read-only evidence at
PHASE8_3_H4C_NATIVE_BOOT_INCIDENT.md and the processed
machine-readable output. New real H4D MUST NOT be
authorized until true official _run_agent initialization
has been tested with a sandboxed ZERO-NETWORK local
provider in a separate disposable rollback environment.
