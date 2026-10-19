# Phase 8.2B — Evidence Integrity and Budget Observability

**Status (2026-10-19): SCOPED NATIVE MOCK E2E PASS. Real StepFun post-change E2E NOT RUN. Active NOT AUTHORIZED.**

Phase 8.2B now has both an offline Evidence Contract and newly verified **native Agent execution** with a locally simulated main-model Provider. A successful native Mock test is not evidence of StepFun reasoning quality, real token expenditure, subscription billing, statistical speed improvements or production readiness.

## 1. Frozen baseline and isolation

| Subject | Value |
|---|---|
| Public GitHub baseline | `b47a0d39c13661c0f73a247f6898ff33b186948f` (merged Phase 8.2A, PR #7) |
| Frozen 8.2B native test source | `9172e6dbed4b7c7f744480de9a95668685fe9b22` |
| Branch | `feat/phase8-2b-evidence-budget`, Draft PR #8, **not merged** |
| NAS main | `afa2512cc66400d111c28cb5fe00e9f83fdba49a`, untouched |
| Hermes | Real native CLI/tool flow; independent test-only Hermes Home and plugin copy |
| DSH | Real resident native SDK JSON-RPC, pinned upstream `477b4f420553e8a52c2fbccc464d7561b239c443` |
| Main Provider | Local HTTP Mock, never StepFun's network |
| Healthy Runtime | Local deterministic rule Mock, **not Laya MLX** |
| Runtime-down | Real local HTTP 503 from isolated Shadow transport |
| Raw evidence | Git-ignored private SQLite/SDK/HTTP/logs and HMAC secret; never in public source |

All seven reported native Mock executions were performed **after commit and on a clean frozen source**. Follow-on documentation/tests do not retroactively replace the frozen tested implementation.

## 2. Deliverables and reused boundaries

Prior Phase 8.2A already achieved its explicitly bounded real-Provider native Shadow E2E, but some HTTP observations relied on sequential time windows. Its historical results must not be promoted to proof of 8.2B's newly instrumented source.

Phase 8.2B adds:

- `local_system_one/evidence_integrity.py`: strict, versioned model/platform-neutral evidence types; independent Task Outcome, Agent Execution Outcome and Evidence Integrity; conditional capability coverage; conflicts and missing evidence are never guessed away.
- `local_system_one/budget_observability.py`: reconciles controlled upstream proxy reservation, attempt, real response and unknown outcome, separately from Agent self-reported logical calls, Runtime calls and billing/usage.
- `scripts/phase8_2b_native_correlate.py`: independent **private** native SDK/SQLite to Adapter HMAC to Runtime HTTP correlation, requiring exact identity rather than clock proximity.
- `scripts/phase8_2b_verify.py` and three synthetic fixture families: standalone public offline contract and OFF/Shadow comparisons.
- Isolated opt-in Hermes and DSH correlation extensions. In production these remain off and never gain Active tool authority. DSH's optional SDK exporter is bounded, metadata-only and confined to isolated private storage.

An initial Hermes Mock attempt failed the independent verifier because the tool-result probe and turn-end observer reused an identical Gate request ID. The opt-in isolated test path now issues a unique ID for each request while retaining native identity through scoped keyed references. That failed exploratory attempt was excluded from formal evidence.

## 3. Native Mock execution evidence

The Mock main Provider supplied explicit tool calls to the *real platform-native tool*. The hidden input file marker was absent from the user request. The independent verifier checked the original file content against actual native tool results **and** final assistant output; Agent self-assertions alone did not count.

| Native scenario | Paired native tool calls | Controlled Mock Provider requests | Runtime HTTP | Exact native-to-HTTP correlation |
|---|---:|---:|---|---|
| Hermes OFF | 1 | 3 | 0 | N/A |
| Hermes healthy Shadow | 1 | 3 | 200, 200 | **2/2 PASS** |
| Hermes Runtime-down Shadow | 1 | 3 | 503, 503 | **2/2 PASS** |
| DSH native SDK OFF | 1 | 2 | 0 | N/A |
| DSH native SDK healthy Shadow | 1 | 2 | 200, 200 | **2/2 PASS** |
| DSH native SDK Runtime-down Shadow | 1 | 2 | 503, 503 | **2/2 PASS** |
| DSH SDK two Turns + second Session | 3 | 6 | six HTTP 200 | **6/6 PASS** |
| **Total** | **9** | **21** | **14 observations** | **14/14** |

The multi-Turn scenario is a **single genuine SDK process**, two Turns of one Session plus a Turn of another Session. The verifier checks SDK turn/start/end and paired tool/call/results, unique Adapter IDs and the exact originating Runtime request. Arbitrary time-window joins cannot pass.

Frozen privacy-safe aggregate: [Phase 8.2B Native Mock Acceptance](../results/processed/phase8_2b_native_mock_acceptance.json). Original event streams, file contents, platform identities, key material and complete test tasks remain privately ignored.

## 4. Budget reconciliation

All **21** loopback Mock requests had matching durable `reserved`, `attempted`, `responded` and proxy-local `result` lifecycle records, without cap overflow. This establishes observed counts only for monitored mock egress; it does not establish system-wide egress enforcement or actual Provider charges.

| Field | Hermes | DSH |
|---|---|---|
| Physical mock proxy requests | 3 per case | 2 per single-Turn case; 6 multi-Turn |
| Main Agent reported logical calls | 2 per case | Not reliably attributable; **unknown** |
| Unattributed physical requests | **1** per case | **unknown**, not assumed zero |
| Cost / subscription debit | **unknown** | **unknown** |
| Provider-verified token counts | **unknown** | **unknown** |
| Reconciler status | **PARTIAL** for unknown usage/billing | **PARTIAL** for unknown usage/billing |

Do not interpret the extra Hermes request as a retry, auxiliary event, or free request. A local Runtime 503 is a Shadow observation failure, not proof of failure in the Provider proxy or main Agent.

## 5. Acceptance matrix

| Dimension | Status | Exact scope |
|---|---|---|
| Evidence Integrity | **PASS (native Mock scope)** | 14/14 independent native ↔ Adapter ↔ HTTP links |
| Budget lifecycle counts | **PASS (controlled Mock scope)** | 21/21 attempts/responses against pre-send caps |
| Budget usage and actual charges | **PARTIAL / UNKNOWN** | No real Provider invoices, tokens or credit tracking |
| Cross-platform Contract | **PASS (bounded scope)** | Hermes + DSH native Mock and synthetic third Adapter |
| Native E2E Regression | **PASS (Mock scope)** | Seven fresh bounded native task executions |
| Real StepFun post-change E2E | **NOT RUN** | 8.2A real-provider evidence is historical only |
| Performance and production reliability | **NOT EVALUATED** | One artificial read-only task family; not statistically representative |
| Active readiness | **NOT AUTHORIZED** | No new stop, retry, tool mutation, Provider switch or deploy permission |

This is a **scoped engineering acceptance**, never a blanket production PASS.

## 6. Privacy, provenance and licensing

- Only allowlisted metadata and aggregate counts are committed; raw SDK frames, native Session/Tool IDs, file paths, task/tool content, HMAC keys, auth headers and real-model credentials remain excluded under `private/`.
- The test-only correlation key is ephemeral/private and never in PR or public fixtures. Hash equality does **not** authenticate independently the source of a fabricated log.
- The independent verifier refuses duplicate, orphaned, cross-Turn, cross-Session or conflicting identity; unavailable evidence stays missing/partial.
- No JevAny code, weights, datasets, prompts, figures or runtime dependencies were copied. JevAny was referenced only for methodology and intellectual framing. Apache-2.0 project source and existing third-party notices are preserved.
- NAS `main`, production Hermes/DSH, Gateway, credential pools, Laya thresholds and Canary authority are untouched.
- Codex Review was disabled by the maintainer and its absence does not imply approval.

## 7. Reproducibility and remaining gate

Offline public validation:

~~~bash
python scripts/phase8_2b_verify.py \
  --bundle tests/fixtures/phase8_2b/all.synthetic.jsonl
~~~

Real-source native correlation checker:

~~~text
scripts/phase8_2b_native_correlate.py
  --platform hermes|deepseek_harness
  --private-key-file <private file>
  --native <private isolated SQLite or SDK JSONL>
  --adapter <private sanitized Adapter JSONL>
  --http <private Runtime HTTP JSONL>
  --output <new private result file>
~~~

The private native runner is **not shipped publicly**; its raw files may contain real platform-generated prompts and identifiers. The public release includes the sanitized frozen summary, verifier, tests and contract.

**Full regression at this checkpoint (2026-10-19): Python `951 passed`; DSH Vitest `64 passed`; TypeScript typecheck PASS; DSH build PASS; release sanitizer and public-file allowlist unit test PASS.** The final committed source still requires a fresh `publish_ready=true` clean-release check; its result is recorded on Draft PR #8 after the final push. A passing release build does not authorize merge or deployment.

Before changing production authority, future work still needs independent real-Provider post-change evidence (if explicitly authorized), more tool types, crash/partial-side-effect scenarios, concurrency/stress, calibrated model quality and representative runtime-overhead testing.
