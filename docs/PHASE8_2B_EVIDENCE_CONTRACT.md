# Phase 8.2B — Evidence Integrity Contract v1

Status: **implemented offline schema and verifier; exact native cross-layer correlation not yet independently attested**. This is an additive verification contract, not Adapter Contract v2, a replacement Runtime API, a new Gate, or an execution/Canary authorization.

## 1. Baseline and reuse audit

Public source baseline: GitHub main b47a0d39c13661c0f73a247f6898ff33b186948f (Phase 8.2A, merged PR #7). NAS local main afa2512cc66400d111c28cb5fe00e9f83fdba49a remains unchanged.

Existing components preserved:

- Adapter Contract v1: stable Gate semantics, Decision Envelope, Action Outcome, strict validation and platform-specific authority inside adapters.
- Phase 8.2A real Hermes/DSH native tool/turn verifiers: independent task oracle verification from **private** SQLite/SDK events. They remain the authority for their exact bounded native scope.
- The isolated HTTP Shadow proxy: metadata-only Runtime forwarding, now with an optional shared secret reference for request correlation.
- The StepFun Plan Provider budget proxy: cross-process pre-send reservations, loopback-only endpoint, configured per-run and global caps.
- Public release allowlist and sanitizer, regression checks and existing safe-fail observability logic.

Gaps before this phase: native events and HTTP observations were often assigned to a sequential isolated time window, *not a proven causal link*. Agent logical API-call counts did not represent all physical proxy attempts. Adapter event IDs are platform-specific; some are random and not mapped to a native Turn. Nothing in this phase retroactively invents that mapping.

## 2. Versioned minimal evidence format

Implementation: local_system_one/evidence_integrity.py. Current frozen schema name: local-system-one/evidence-v1.

An event has a strict field allowlist. Required fields are schema, event_ref, run_id, platform, kind, stage, refs, evidence_source and evidence_status. Optional fields: parent_ref, gate, decision_source, decision_model, execution_backend, raw_recommendation, guarded_recommendation, adapter_action_status, policy_version, ts_unix_ms, outcome.

A run may additionally include observed_elapsed_ms with an explicit timing_source.
The verifier passes through the measurement rather than inferring it from
asynchronous event timestamps. Comparing a single OFF/Shadow pair is descriptive
only; missing performance data remains null, not an invented zero-overhead claim.

Kinds:

1. native_event (including native tool_call/tool_result/turn_end)
2. adapter_observation
3. decision_request
4. runtime_decision
5. shadow_outcome
6. agent_execution
7. independent_verification

Every event_ref and refs value is a 32-hex opaque identifier. The allowed refs keys are session, turn, native_event, tool_call, decision_request, runtime_decision and provider_attempt. They are **references**, not original platform IDs. Only bounded identifiers, enums, finite timestamps and allowlisted decision labels may be exported.

For real isolated runs, generate refs in private space with opaque_ref(secret, scope, original_id), using an independent 32-byte random key per run. Reuse the same key for matching stages; keep the key and original values private. Different scopes cannot be joined accidentally. Synthetic fixture refs are deterministic and **not** security proofs.

Example (shortened here, see tests/fixtures/phase8_2b/ for valid complete records):

~~~text
native_event(tool_result) -> adapter_observation -> decision_request
  -> runtime_decision -> shadow_outcome
native_event(turn_end) -> agent_execution -> independent_verification
~~~

Each arrow means parent_ref points to the *exact* event_ref of the parent. Nested refs must be compatible in run, platform, session, turn, tool and decision request, whenever both are declared. Event order is irrelevant. Timestamps never establish parentage.

If the Runtime is down, a shadow_outcome may refer directly to the attempted decision_request: **no fictional runtime_decision is created**. When mode is OFF no Decision Gate call is required.

Duplicate event refs, inconsistent ancestry, cross-Run/Turn/Session references, contradictory outcomes and wrong tool-ID reuse block verification. Missing ancestry, unsupported identities, orphan/unpaired native tool stages, absent independent task attestations and unsupported capabilities remain visible rather than treated as a successful cross-layer trace. Fully missing parents are PARTIAL; dangling explicit parents and contradictory links are BLOCKED.

Current bounding: 10,000 events per run, 100 runs per verification bundle, and bounded identifiers. Expired or dropped evidence must be represented as missing/partial; the validator cannot restore lost raw evidence.

## 3. Evidence provenance, confidence and authority

Evidence sources: native_observed, independently_verified, platform_reported, model_reported, estimated, unknown.

Evidence states: verified, partial, ambiguous, missing, unsupported.

**Task Outcome**, **Agent Execution Outcome** and **Evidence Integrity** are separate:

- Task PASS/FAIL requires a verified independently_verified event from the **independent oracle**, not a model's final answer.
- Agent PASS/FAIL requires a verified native-observed or independent execution event.
- Evidence PASS requires a complete, structurally consistent trace relative to explicitly declared mode/capability requirements.
- Missing proof gives UNKNOWN/PARTIAL; identity conflicts give BLOCKED.
- A forged/incorrect independent-verifier record can still pass a *structural* check. Offline sanitized evidence cannot replay a secret file-content oracle. The source-specific private verifier must attest to that oracle separately. HMAC reference matching is not source authentication, tamper-proof logging or an authorization grant.

The observed recommendation and its guarded form are two distinct optional labels; a decision recommendation is never authority to execute it. No execution action is changed by this module.

## 4. Capability declarations

Implementation: validate_capabilities(). Minimal dictionary of seven capability names:

tool_result_observation, turn_identity, session_identity, model_usage_reporting, request_attempt_observation, provider_budget_enforcement, independent_outcome_verification.

Each is supported, unsupported, conditional or unknown; source is a bounded identifier, and conditional requires an explicit bounded condition alias.

Real current coverage notes:

| Capability | Hermes isolated 8.2A | DSH isolated 8.2A |
|---|---|---|
| Native tool result | Conditional, SQLite/plugin inspection | Conditional, native SDK observer |
| Native Session/Turn | Conditional, platform event/session shape | Conditional, SDK session/turn lifecycle |
| Agent model-call usage | Partial self-reported logical counts | Conditional SDK step-end usage; not all HTTP attempts |
| Hard external request cap | Conditional, correct isolated loopback route required | Conditional, controlled isolated egress required |
| Independent task verifier | Conditional, private byte oracle | Conditional, private native read/output oracle |
| Exact native-to-HTTP request ID | **Unproven** | **Unproven** |

Do not copy the synthetic fixture's intentionally fully supported capabilities into a real run without evidence. Missing or conditional capabilities are Coverage Gaps, **not** default permissions or guessed values. Per-platform extraction remains inside adapters/private harnesses; only sanitized normalized records reach this tool.

## 5. Optional 8.2B HTTP request correlation

The existing scripts/phase8_2a_shadow_proxy.py supports --run-id and --private-key-file. The key must be an existing ignored private file with restrictive permissions, at least 32 random bytes, underneath the repository's private/ directory. The proxy never logs the key, original request ID, header, task or response body. A separate private normalizer can independently calculate the same decision_request_ref using the same secret and scope string decision_request.

The proxy now emits decision_request_ref, event_ref, run_id, response_matches_request_id (true/false/null) and correlation_status; it preserves legacy request_hash for backward compatibility. A matched proxy reference alone **does not connect a native event to that request**. For complete proof, a platform-specific private exporter must observe the original native event and request-ID pair, normalize both, and produce the explicit link. None is invented by matching invocation times.

## 6. JevAny methodology boundary

Public methodology reference only: https://github.com/SimpleJev/JevAny and its published Agent harness analysis. Task difficulty, delegation degree, coverage, quality and cost should be evaluated independently; a model's choice among bounded candidates is not an execution authorization. This project does **not** import, copy, modify, train or redistribute JevAny source code, package, weights, data, examples, prompts or figures.

Methodological ideas, source-code provenance, runtime dependencies, model weights and data assets are separate licensing categories. Both repositories disclose Apache-2.0 for relevant code, but the absence of third-party code copying reduces rather than eliminates intellectual-property obligations. Preserve existing third-party notices.

## 7. Contract consistency fixtures and independent CLI

- tests/fixtures/phase8_2b/hermes.synthetic.json
- tests/fixtures/phase8_2b/dsh.synthetic.json
- tests/fixtures/phase8_2b/contract_only.synthetic.json
- tests/fixtures/phase8_2b/all.synthetic.jsonl (cross-platform frozen sample)

Run from the repository root:

~~~bash
python scripts/phase8_2b_verify.py \
  --bundle tests/fixtures/phase8_2b/all.synthetic.jsonl \
  --output /tmp/system-one-8_2b-report.json
~~~

No main model, decision model, Hermes/DSH SDK, credentials or external requests are needed. The frozen fixtures prove the normalized **tool contract** across platform labels, not native E2E behavior or a real Provider bill.
