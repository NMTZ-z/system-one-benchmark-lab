# Phase 8.3A — H4 missing-file + DSH native prerequisites

**2026-10-22 — ENGINEERING-ONLY qualification. Zero new real StepFun
requests. H4 and DSH D1–D4 native Provider-backed tasks NOT RUN.**
**GitHub PR #9 remains Draft; Active/Canary NOT AUTHORIZED.**

This work follows real Hermes H1/H2/H3 one-shot executions.
Real H3 Runtime-down fail-open, H2 healthy Laya/MLX Shadow and H1
read-only tool success have already been independently adjudicated.
The first original H1 physically attempted Provider request still has
no terminal evidence, so global Phase 8.3A is still BLOCKED.

## 1. H4: define the original failure oracle before main-model execution

The Phase 8.3A protocol predeclared a failing native read-only file
tool task, rather than another successful read. The pre-existing
8.2A native runner supported read_nonce and file write but not a
negative read scenario; running it directly could have mistaken an
Agent's final error claim for authentic tool evidence.

A NEW H4-only scenario read_missing is now permitted only when:
- Platform is official isolated Hermes and case ID is h4_missing_read.
- Gate mode is Shadow, with no Active/Canary authority.
- Main StepFun model can reach only the local 18794 capped outlet.
- The native task executes in a newly created, Git-ignored, restrictive
  folder under the project's existing private H4 root.
- Maximum 90 s Agent time, 24 shared global physical StepFun attempts,
  at most three H4 attempts, count/ledger reserved before network I/O.
- Main model prompt requests exactly ONE native read_file of a new
  randomized basename, and explicitly forbids creating, rewriting,
  retrying or substituting a path.
- A private, restrictive PRE-AGENT target manifest records the exact
  original missing path and its digest. The target file is not created.

The independent H4 negative-result oracle requires:
1. The exact original manifest target is absent before and after,
   including no dangling symlink or success output file.
2. Exactly one original isolated Hermes SQLite Session for that
   case folder, one native read_file call, one matching result
   tool_call_id, no other native tool or hidden action.
3. The native tool's structured returned JSON contains
   not_found=true and an explicit nonempty "File not found:" error;
   successful file bytes must be absent.
4. Original model tool-call arguments point to the EXACT preregistered
   missing path, rather than a model-generated substitute.
5. The native session provider route and normal completion must
   match the strictly pinned test identity.

The Agent's final prose alone can NOT establish a failure; until
separately human/independently checked, its semantic truthfulness is
NOT AUTOMATICALLY VERIFIED.

### Real Hermes tool implementation evidence, no Provider

Using the actually installed Hermes file tool in the isolated Home,
with zero StepFun requests and no Agent session, an intentionally
absent private file returned typed JSON fields:
- error: nonempty "File not found: ..." (private path not exported);
- not_found: true; content: empty;
- file absent before and after;
- Hermes actual post_tool_call observer classification helper returned
  status=error and error_type=tool_error.

This proves the error can be translated into the native typed failure
payload the Retry plugin requires, not that a complete Agent run
actually dispatched the event.

The Retry Shadow plugin explicitly requires native status
error/failed/timeout/cancelled and trusted tool identity. It must
NOT infer retry permission from raw error text, since side effects
and tool-outcome provenance would be ambiguous. Its existing policy
marks retry_budget_available=false when attempts/time budget are not
independently verified. No automatic retry is authorized.

**H4 qualified in the limited sense of isolated negative-tool oracle
and typed failure classification: PASS_OFFLINE. H4 native end-to-end
and Retry Gate observed-in-real-Agent status: NOT RUN / NOT VERIFIED.**

## 2. Immutable global physical Provider budget

The original 30-event H1+H2+H3 Provider ledger SHA-256 is still:

5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb

- H1 slots 1–3: three attempted, two real HTTP 200, ONE UNKNOWN.
- H2 slots 4–6: three attempted and three real HTTP 200.
- H3 slots 7–8: two attempted and two real HTTP 200.
- H4 has reserved/attempted: ZERO.
- Total: 8/24 physical reservations used; 16 nominal slots remain.
- Billing amount, StepFun Plan credit deduction, token savings:
  UNKNOWN / NOT MEASURED.

The updated append-only auditor now recognizes future H4 ONLY on
new slots starting at 9, with a cap of 3. It preserves all original
H1, H2 and H3 SHA-authenticated bytes and terminal outcomes, and
rejects unknown run IDs, out-of-order/repeated slots and any
alteration of previous frozen records. A local simulated H4
append was tested without making a real request.

**Do not reset the original ledger or interpret the remaining 16
slots as an unconditional paid Provider allowance.**

## 3. DeepSeek Harness D1–D4: independent secure-input design

The pinned actual native DSH checkout remains at commit:

477b4f420553e8a52c2fbccc464d7561b239c443

Real DSH SDK OFF and Shadow had already completed initialization
and shutdown with **no key** supplied and zero main-model calls.
That configuration smoke was rechecked. Both patched SDK profiles
are 0600 files inside a 0700 Git-ignored private directory.

The new DSH offline gate independently verifies:
- only the pinned compiled native DSH CLI and local Adapter build;
- StepFun step-5-preview as the ONLY configured main model;
- openai-completions wire format;
- baseURL fixed to http://127.0.0.1:18794;
- exactly one API-key **environment variable name**
  STEPFUN_API_KEY, with no token value in YAML or public Git;
- provider retryPolicy.maxRetries = 0;
- only OFF / Shadow policy, no acknowledged Canary, no Active;
- the exact existing physical H1/H2/H3 budget prefix;
- a subprocess environment which never inherits Hermes Home,
  previous tokens, alternate Provider keys or HTTPS proxy overrides.

For a future real run, the owner must enter a **separate DSH
credential through a trusted local interactive prompt**.
The secret stays only in the individual DSH subprocess memory/
environment. The Project cannot read the Hermes test Home's
auth.json, production .env or other credentials, and does not
save a DSH token to files, Git or logs. Because the DSH SDK
currently specifies apiKeyEnv, process-environment exposure
within the operating system is a residual privacy consideration:
do not use an unrestricted inherited shell environment.

A separate **real, one-shot DSH executor with a live capped Provider
outlet and evidence oracle is not yet authorized or implemented**.
Consequently DSH StepFun real-native credential readiness is
BLOCKED_PENDING_OWNER_SECURE_INPUT, even though OFF/Shadow
configuration and native SDK initialization are already PASS_OFFLINE.

## 4. DSH native provenance checks, without model requests

The new structural verifier requires native SDK session.event
frames to contain a single coherent:
turn/start → tool/call → tool/result → turn/end.

Call/result IDs, native Session/Turn IDs and actual read tool name
must agree. For D1/D2/D3 read-success scenarios, typed
message.isError must be false. For D4 native missing-file read,
message.isError must be true. A final answer, exact original file
bytes, and native-to-Adapter-to-HTTP HMAC linkage **are not
established by this structural test alone**. These must be
independently verified in future actual native DSH runs.

Deliberate forged/missing/cross-Session/duplicate event fixtures
are rejected. This never exports real Session IDs, tools, prompts,
HMAC keys or original file content.

## 5. Gating decision

| Workstream | Qualification |
|---|---|
| H4 original missing-target oracle | PASS_OFFLINE |
| Hermes actual file tool returned native structured failure | PASS_OFFLINE |
| Hermes typed observer error derivation | PASS_OFFLINE |
| H4 native Agent + StepFun + real Retry Shadow | NOT RUN |
| H4 robust negative tool-result/Agent outcome attribution | Prepared, not live verified |
| DSH OFF / Shadow native SDK init/shutdown | PASS_OFFLINE, zero Provider |
| DSH strict provider config and security tests | PASS_OFFLINE |
| DSH typed native tool event structural provenance | PASS_OFFLINE on synthetic frames |
| DSH independent real-provider credential | NOT PROVISIONED |
| DSH D1–D4 real native E2E | NOT RUN |
| H1 historical provider slot 1 | STILL UNKNOWN |
| Phase 8.3A overall paid Provider budget/cost | BLOCKED / UNKNOWN |
| Production Active/Canary | NOT AUTHORIZED |

**Recommendation after this offline work:** the next narrowly scoped
real evaluation should be one H4 read-only failure on the EXISTING
StepFun Plan, only after its full one-shot Agent/Provider evidence
runner is frozen and approved. DSH real runs require the independent
owner-entered credential and separately safe capped executor. Do not
launch either paid route merely because the offline SDK/contract
tests pass. No extra Gate or Active is justified by this phase.


## 6. Completed offline regression and publish gates

The full Phase 8.3 branch was retested after the H4-only negative
scenario, native-structured error oracle, immutable global H4 slot
logic and independent DSH secure-input/native-event guards:

- Python full test suite: **1201/1201 PASS**.
- DSH native adapter Vitest: **64/64 PASS**.
- TypeScript typecheck and DSH build: **PASS**.
- Native Hermes direct missing-read probe: **PASS_OFFLINE**
  (actual missing-file typed error/status with 0 main Provider calls).
- DSH official SDK OFF/Shadow initialize/shutdown: **PASS_OFFLINE**
  (no Provider key supplied, 0 native task/model requests).
- Original H1+H2+H3 private ledger SHA and historical
  H1/H2/H3 verdicts remain unchanged.
- Public sanitizer preview: passed and contained **283
  allowlisted files**, subject to final clean-source revalidation.

No H4 or DSH paid/provider-backed experiment was run.
No new StepFun plan calls, Laya Active controls, GitHub main
merge, NAS Forgejo main changes or production Home changes occurred.
The eventual real H4 run also needs a separately frozen one-shot
Provider/Agent driver and independent live error-hook evidence before
its results could be accepted, even though the preflight is ready.
