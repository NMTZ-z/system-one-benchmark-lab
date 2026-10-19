# Phase 8.2B — Budget Observability and Reconciliation v1

Status: **controlled-output attempt lifecycle extended; offline reconciliation implemented; upstream billing is not independently observable**.

## 1. Scope and what is counted

The earlier 8.2A Provider Cap remains the **only** live budget-enforcing HTTP outlet in this phase. This is not a generic paid-provider router. Its existing localhost access rule, approved StepFun Plan URL and model, private ledger path, explicit --execute-real-provider acknowledgement, limits and before-I/O fcntl reservation are retained.

The new local_system_one/budget_observability.py reads that private ledger after a run; it does not send Provider traffic or change Adapter decisions.

Three different denominators must stay separate:

| Counter | Source | Meaning |
|---|---|---|
| Agent logical calls | Native Agent report | Self-reported LLM API calls, potentially excluding auxiliary or internal traffic |
| Controlled Provider proxy attempts | Outlet-marked attempted entries | Number of outgoing network I/O attempts initiated by this proxy |
| Decision Runtime calls | Separate collected evidence | Gate requests, deterministic rules, model inference, failures and timeouts, not necessarily paid main LLM calls |

Hermes' recorded 8.2A result of **2 Agent self-reported calls vs 3 real forwarded proxy requests per case** is not a known retry count. The new ledger exposes unattributed_requests=1 when this exact 3-versus-2 comparison is supplied. No guessed billing, hidden-reasoning or auxiliary-call classification.

## 2. Append-only lifecycle

Existing on-disk records are retained:
- reserved: atomically before any outgoing upstream attempt; consumes a slot permanently;
- result: final **proxy-local** HTTP response status and local duration (legacy 8.2A compatibility).

Additional records emitted by the **same** Phase 8.2A proxy:
- attempted: durable marker immediately before initiating outbound urllib I/O;
- responded: an actual upstream HTTP status was received (HTTP errors such as 503 still qualify);
- outcome_unknown: outbound I/O was attempted but the upstream result was not conclusively received.

The offline contract also recognizes failed and reconciled event types for normalized ledgers, but the current live proxy does not fabricate those classifications when it cannot know the upstream outcome. A local HTTP 502 due to timeout is *not* a known remote failure or a confirmed bill. reserved != attempted != responded != task success.

The existing 8.2A log format with only reserved/result can still be loaded. In that case proxy_attempts is explicitly **null**, legacy_8_2a_counts_only=true, and reconciliation is PARTIAL rather than spuriously exact.

Atomicity: cross-process fcntl lock protects reserve/read/append against concurrent same-ledger attempts, and fsync is used for the journal. Reserving at the controlled endpoint is independent of upstream success; no refunds for lost responses. Under an interrupted write, a reservation remains consumed and the verifier reports incomplete evidence. It must never reset the cap optimistically.

## 3. Cost, tokens and unknowns

Optional per-slot usage may be provider_reported, invoice_confirmed, estimated or unknown.

- input/output token sums are reported only for measured Provider-reported or invoice-backed usage.
- A provider response without a usage field leaves usage unknown.
- confirmed_cost requires invoice_confirmed provenance; inferred pricing cannot be called confirmed.
- estimated_cost is separate. Unpriced or missing slots increment unknown_cost_requests.
- A deterministic rule decision **does not count as a model inference**.
- Decision Runtime request counts and actual local model-inference counts must be independently sourced. The reporting tool never derives them from the number of network Provider requests.

No raw prompts, completion contents, Authorization headers, API keys, model-provider account details or private paths belong in the public ledger. The small allowlisted numeric usage fields are the only supported exported usage records.

## 4. Hard-cap and failure policy

The actual guarantee is:

> No more than total_cap / per_run_cap requests through the correctly configured, monitored proxy will be *initiated* by that proxy.

It is **not** a system-wide charge cap if the Agent/SDK can bypass the outlet or use an uncontrolled connection. The caller must verify the isolated model endpoint/credentials before a real experiment. Hermes previously had a credential-pool endpoint-precedence trap; the updated Phase 8.2A preflight already blocks uncapped routing. DSH and other platforms need equivalent coverage. The offline verifier requires controlled_egress_verified=true; otherwise budget_integrity=BLOCKED.

Three distinct safety responses:

1. Shadow observation fails: original Agent operation continues (observational fail-open).
2. Authorized test budget exhausted or ledger corrupted: the controlled outbound request is refused before upstream I/O (fail-closed for budget).
3. Evidence is missing, ambiguous, duplicated or contradictory: the acceptance result cannot PASS (verification block/partial, never fabricated success).

Do not restart production services, rotate to a second paid Provider, reset paid credentials, automatically retry a tool, or authorize Active behavior to make a test pass.

## 5. Budget reconciliation

Reconciler: local_system_one/budget_observability.py::reconcile_budget.

Inputs: full sanitized ledger event list, run ID, global/per-run caps, optional native logical-call count, independent Runtime counters, optional usage provenance and explicit controlled-exit attestation.

Checks include duplicate reservations, orphan lifecycle events, duplicated terminal outcomes, overlapping run identities, overspending, missing local finishes, provider-response attribution, unsupported usage, missing accounting, and bypassed/unverified egress.

Output keeps:

- reserved_run, reserved_total;
- proxy_attempts (null on legacy uninstrumented ledger);
- provider_responded, transport_failed, outcome_unknown, attempted_unresolved;
- agent_reported_model_calls, unattributed_requests, agent_calls_exceed_attempts;
- decision_runtime_calls;
- provider_reported_input_tokens/output_tokens, confirmed_cost, estimated_cost, unknown_usage_requests, unknown_cost_requests;
- budget_integrity PASS/PARTIAL/BLOCKED plus explicit issues.

A missing or unknown resource is not silently treated as 0, except count metrics for observed known categories where 0 is an actual measured zero.

## 6. Test types and limitations

- Unit/Mock: concurrent pre-send slot race, malformed input and cap enforcement, 200/503 Provider mock, timeout/unknown classification, non-response marker and ledger corruption.
- Frozen synthetic: 3 abstract platform identities × OFF/healthy Shadow/Runtime-down. All IDs and usage are synthetic. Budget reconciliation stays PARTIAL when usage is missing even if event accounting is structurally correct.
- Existing 8.2A native StepFun: original real HTTP traces remain historical evidence only, cannot be retroactively classified by the new attempted/responded records.
- A new, properly isolated native Agent E2E with the new source still needs its own bounded real/Mock Provider and cross-layer evidence bundle before 8.2B native PASS.

These fields measure **observed counts**, not actual Provider billing and not hypothetical Token savings from Shadow decisions.
