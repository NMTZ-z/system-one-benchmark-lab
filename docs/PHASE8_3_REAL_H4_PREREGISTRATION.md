# Phase 8.3A — H4 native failed read + Retry Shadow one-shot preregistration

**2026-10-22: written BEFORE ANY H4 real StepFun Provider request.**
**Frozen Git execution SHA recorded on the subsequent clean prereg commit.
H1/H2/H3 original real Provider history is immutable.**

## Research question and confounding hazards

Can a true native Hermes Agent using the authorized StepFun Step Plan
step-5-preview model attempt to read a disposable absent file, producing
a real typed native error, while the Laya/MLX Completion and Retry
Shadow Gate observers capture correctly paired real traffic without
modifying the Agent?

One actual missing-file result and one native tool call are required.
A final Agent statement about file absence, without the original
native structured result, is NEVER considered proof.
A Retry Shadow observation is not established solely because a
native result JSON contains "error": Hermes must emit a typed
post_tool_call status and event, with an independently keyed identity.
No model-side retry is allowed by System One.

## Frozen source, Model and Provider

- Public GitHub and NAS main remain unchanged. PR #9 stays Draft.
- Original frozen H1 real run SHA:
  82993477667817c8941caa429feea576d091a424.
- Original frozen H2 real run SHA:
  0dc626ff86038702f74027b4a988d21f096f72d9.
- Original frozen H3 real run SHA:
  40a7b4416db07e6eedcf505131e0c9b3e1a98eac.
- Immutable existing first 30 physical StepFun Provider ledger events:
  SHA-256 5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb.
- H1 physical slots 1–3, H2 4–6, H3 7–8. H1 slot 1 has
  no Provider terminal result and stays UNKNOWN.
- H4 only uses slots 9–11, at most three attempts. Total
  original 24-slot physical request cap remains. Never reset,
  refund, or silently finalize H1. Remaining budget does not
  independently authorize use beyond H4.
- Candidate must be committed, with an exact frozen clean SHA
  checked before service/Provider creation.
- The sole upstream Provider is the already-authorized StepFun
  Plan step-5-preview, via fixed budget proxy 127.0.0.1:18794.
  No alternate Provider, pay-as-you-go key or uncapped endpoint.
- Hermes uses only the dedicated private test Home at
  ~/.hermes/system-one-phase83lab. Its existing separately
  manually authenticated key stays in place and is NEVER read
  by the test code.
- Only the TEST Home's publicly committed plugin Python
  source may be updated after the prereg source commit, by
  a strict parent-SHA-matched atomically copied file.
  The H4 plugin change adds opt-in PRIVATE HMAC Retry evidence,
  never Active/Canary control or production mutations.
- Shadow only, title model upgrade disabled only in this Home.
  Automatic nonmodel derived titles remain available.
- Pinned local Laya Typed Decisions 421M revision
  f9ab0b228f0fc0f14d873dbc99038f135c2da1b2
  runs MLX on 127.0.0.1:18782. A dedicated Observer on
  18793 stores privacy-safe keyed request metadata only.
- One isolated native Hermes task with at most 90 seconds
  Agent execution and a bounded 80-second drain for already
  attempted physical Provider requests. No repeated paid
  Agent call or automatic retry.
- One randomly named, guaranteed ABSENT original private file
  is recorded in a file under ignored private storage, with its
  exact original path/digest committed there before native Agent
  execution. The model is prompted to call read_file ONCE,
  report the actual error, and not write, create, shell, browse,
  reroute, retry or infer contents. No other tools are authorized.

## Strict H4 acceptance

1. **Native tool negative oracle**: original Hermes SQLite
   must have exactly one Session for this H4 case, a single
   read_file tool call and a paired tool result with identical
   native tool_call_id. Native tool arguments must equal the
   pre-Agent target manifest. Structured result must contain
   not_found=true and File not found: error, with no content
   or modified/created target. Native Agent exit=0, no timeout.
   The final text's truthfulness is NOT silently inferred.

2. **Completion Shadow**: exact two actual HTTP 200 observer
   events with real Laya MLX backend and true echoed request IDs.
   Native tool_result and turn_end from Hermes SQLite must
   form 2/2 HMAC-linked Adapter and HTTP references. No task
   control may be exercised by the Completion recommendations.

3. **Retry/Escalation Shadow**: one actual HTTP 200 Retry
   observation, one opt-in PRIVATE Adapter record, the same
   original native Session/Tool HMAC as the Completion tool-result
   event, the same keyed turn ref and a unique keyed HTTP
   decision request with actual echo. The resulting decision
   must be a guarded advisory contract choice and must NEVER
   cause Agent tool retry, escalation or mutation. Any missing,
   partial or duplicate identity is a failing criterion.

4. **Original budget**: at most three physically reserved
   StepFun requests for H4 (slots 9–11), all attempts/response
   terminal states properly recorded with no new unknown
   outcome or reset of the original 24-global shared budget.
   A mismatch/uncapped attempt is BLOCKED, not rewritten.

5. **Reversion and public reporting**: the isolated test Home
   restored to OFF, all test service processes stopped, original
   global H1 UNKNOWN preserved, no production changes. Only
   allowlisted aggregated counts/decisions/hashes leave private
   storage. Raw prompts, files, identities, provider payload,
   HMAC keys and credentials never enter Git.

PASS_SCOPED requires all five. Otherwise report PARTIAL_OR_BLOCKED
and do not rerun H4. H1 history means whole Phase8.3A budget integrity
still stays BLOCKED even if H4 scoped verdict is PASS.
No Active/Canary rights or claimed measured billing savings.

## Pre-real execution quality gates

- Offline negative native tool/original SQLite oracle passes.
- Real installed Hermes native tool typed error observer validated
  with zero StepFun requests.
- Private Retry tool identity/HMAC native-to-HTTP join regression
  and malformed evidence tests pass.
- Source and installed test plugin old/new Git byte identity
  checked; only the test Home may update.
- Full Python and DSH regression tests, TypeScript typecheck/build
  PASS, privacy-safe sanitizer and clean source commit.
- Test Home auth/route, correct strict Shadow + title settings,
  pinned local Laya, no occupied test-only loopback ports.
- Original H1/H2/H3 ledger SHA and privacy snapshots intact,
  H4 run files absent and no preexisting H4 reservation.
- One explicitly opted-in real StepFun Plan H4 invocation only.
