# Phase 8.2B — Evidence Integrity & Budget Observability

Status: **DEVELOPMENT / PARTIAL ACCEPTANCE**. Last edited 2026-10-19.

This report separates newly implemented *offline synthetic* test evidence, historical
8.2A *native* evidence and unperformed 8.2B *native* acceptance. Do not take
passing a synthetic contract fixture as a real Agent E2E PASS.

## 1. Git baselines and isolation

- GitHub public main at start: b47a0d39c13661c0f73a247f6898ff33b186948f (merged PR #7).
- Unmerged public PRs at branch creation: zero.
- NAS local development main: afa2512cc66400d111c28cb5fe00e9f83fdba49a, not updated or reset.
- Separate worktree branch: feat/phase8-2b-evidence-budget, based *exactly* on the above public SHA.
- Existing NAS/main untracked uv.lock and all other development worktrees retained untouched.
- Observed Hermes binary from bounded 8.2A: v0.22.1+11.gd923a5e, adapter v0.9.0. Pinned DSH 8.2A SDK: 0.1.7-rc.2, adapter 0.6.0. These are historical 8.2A versions, **not** a new 8.2B installed-platform certification.

## 2. Phase 8.2A audit and reuse

See [Evidence Contract](PHASE8_2B_EVIDENCE_CONTRACT.md) and [Budget Ledger](PHASE8_2B_BUDGET_LEDGER.md).

8.2A provides a real native Hermes / DSH scoped Shadow baseline, independent private native
read oracle, metadata-only Runtime HTTP observer, cross-process atomic Provider Cap, release
sanitizer, and reversible OFF/Shadow/Canary boundaries. Cross-layer exact native event to
HTTP request linkage remains unproven because some collector association used sequential
test time windows. Hermes reported 2 logical calls per case and controlled Provider proxy
observed 3 real requests per case. Count difference remains **unattributed = 1**.

## 3. Evidence Contract and correlation

New local_system_one/evidence_integrity.py defines a separate strict JSON evidence
contract. It supports run/platform/session/turn/tool/request references, explicit
causal ancestry, stage, decision source/model/backend, independent provenance and
separate verified/partial/ambiguous/missing/unsupported status. Optional
reference generation uses per-run HMAC-SHA256 secret (32+ bytes) retained in private space.

Identity conflict, duplicate ID, orphan, cross-run/session/turn mismatch and
contradictory outcomes fail verification. Event ordering and proximity of timestamps
do not create links. Missing ancestry is not silently repaired. Third-party
platform labels are treated identically.

8.2A Shadow observer supports matching private scoped decision_request_ref on its
HTTP boundary. **A native adapter/private exporter has not yet demonstrated a matching
end-to-end native-event reference for new 8.2B runs. This remains BLOCKED.**

## 4. Budget Ledger

Existing atomic pre-send reserve cap retained; its same isolated Provider proxy
now emits attempted before I/O, responded only upon upstream HTTP receipt, or
outcome_unknown when outbound I/O outcome is unknown, while retaining legacy
reserved/result lines. Local 502 != confirmed Provider response or charge.

Independent budget_observability reconciles Agent logical calls, controlled
Provider attempts, Decision Runtime calls, missing usage, unknown cost, confirmed
vs estimated monetary amounts, explicit provider egress coverage and request cap.
For synthetic 2 vs 3, unattributed_requests=1; no retry or free invocation inferred.
Real 8.2A legacy reservations cannot be retroactively turned into new exact
attempted/responded lifecycle facts.

## 5. Capability / provenance description

Seven capabilities, with supported/unsupported/conditional/unknown status, source
and optional condition. Real Hermes and DSH native hook identity, usage,
credential route and independent verification are conditional, not universally
present. Missing capability gives Coverage Gaps and partial verification,
never fake fields or permission.

## 6. Generic independent verifier and use

Run from repository root:

~~~bash
python scripts/phase8_2b_verify.py \
  --bundle tests/fixtures/phase8_2b/all.synthetic.jsonl \
  --output /tmp/local-system-one-8-2b-verification.json
~~~

The CLI reads privacy-safe frozen JSON or JSONL, produces separate Task Outcome,
Agent Execution Outcome, Evidence Integrity, Budget Reconciliation and matched
OFF/Shadow healthy/Shadow Runtime-down comparison. No Laya or Jev model,
Hermes/DSH install, real Provider, API key, Web dashboard or new service is needed.

The private independent task oracle must **first** truthfully attest to a task
before its sanitized attestation can be compared. Structural verification
alone cannot establish that a private file was actually read or written.

## 7. Contract fixture and regression inventory

Frozen fixture family:

- tests/fixtures/phase8_2b/hermes.synthetic.json
- tests/fixtures/phase8_2b/dsh.synthetic.json
- tests/fixtures/phase8_2b/contract_only.synthetic.json
- tests/fixtures/phase8_2b/all.synthetic.jsonl
- tests/fixtures/phase8_2b/SHA256SUMS

All are *synthetic*, with no native Agent use or real money. They demonstrate
three independent platform labels and three run modes, fully structurally
consistent paths and intentional missing usage. Negative tests cover
duplicate/orphan/causal mismatch, ID scope, missing identity/capability,
unknown usage and transport, concurrency, pre-send hard caps, overspend and
bypass rejection. Source code remains platform-neutral.

## 8. Real native E2E and limitations

**Not rerun for Phase 8.2B.** The inherited 8.2A frozen native scope PASS still
exists and has not been invalidated by this additive offline work, but it does
not establish new evidence-HMAC/HTTP-native correlation, new budget lifecycle
telemetry or new instrumented performance regressions on real Agent platforms.
Provider-backed real experiments need fresh isolated auth, exclusive route audit,
explicit finite caps and credential owner authorization. They have not been
performed merely to produce a green status. Even a Mock-only source test cannot
be substituted for a real native Agent E2E record.

## 9. Privacy and JevAny licensing audit

No JevAny Python package, source-code lines, Git Submodule, model weights,
prompts, datasets, test fixtures or diagrams imported. Public JevAny work is
cited as design-methodology context only; there is no runtime dependency.

Source/code/reference, runtime dependencies, model weights and datasets have
distinct provenance. Independent implementation does not absolutely eliminate
IP risk. No production user requests, native Session IDs, raw tool parameters,
transcripts, internal resource paths, Provider headers or credentials belong
in the public allowlist. HMAC refs indicate private-keyed equality, **not**
independent source authentication or tamper-proof storage.

## 10. Test evidence (update after final run)

- New Phase8.2B Python test set: **35 tests** (32 integrity/contract and 3 controlled
  transport tests); all included in the full Python rerun.
- **Full Python final rerun: 932 passed**. Two interim failures (8.2A
  test-server optional correlation-key backward compatibility and the missing
  in-progress final-report allowlist path) were fixed before the final run.
- Synthetic cross-platform verifier: 9/9 structural evidence PASS, 3 mode
  comparisons COMPLETE, cross-platform contract PASS for *synthetic* cases.
  Synthetic budget integrity PARTIAL because usage/cost are unknown; all
  known 3 requests vs 2 logical calls show unattributed_requests=1.
- **DSH npm tests: 58 passed**, TypeScript `npm run typecheck` PASS,
  `npm run build` PASS (isolated npm ci --offline).
- Hermes plug-in unit/contract tests: PASS as part of 932 Python tests.
- **Public allowlist and sanitizer: PASS** in full Python regression
  (`tests/test_public_release.py`); Apache-2.0 LICENSE and metadata preserved.
- Standalone clean-source public release build **PASS**: 210 allowlisted files,
  source_dirty=false, license_status=included, publish_ready=true at source SHA
  5619f9ce4357be93948a8ced248944c99fddbabe. After this documentation-only
  PR-status update, the final commit must be rechecked for clean publication.
- Frozen native 8.2B source post-fix: **NOT RUN**; no paid Provider requests were generated in Phase 8.2B.
- Performance profiling: not performed; no new claims of zero overhead.

## 11. Changes, publication and regression scope

New code: local_system_one/evidence_integrity.py,
local_system_one/budget_observability.py, scripts/phase8_2b_verify.py,
tests/test_phase8_2b_integrity.py and static fixtures.

Reused/minimally extended: scripts/phase8_2a_provider_cap.py,
scripts/phase8_2a_shadow_proxy.py, release/public-files.txt. New documents:
this report, Evidence Contract and Budget Ledger. Existing Adapter Contract
v1 and all Gate thresholds are unchanged. No new model/Agent Adapter,
active tool control, provider switching, installation or deployment.

GitHub **Draft PR #8**: https://github.com/NMTZ-z/system-one-benchmark-lab/pull/8
(initial source commit 5619f9ce4357be93948a8ced248944c99fddbabe).
Open, **not merged**; no production deployment. Codex Review was disabled
by the maintainer in prior project configuration and has not been assumed
to run or return any result. Subsequent commit SHA must be checked on PR
before any maintainer merge decision.

## 12. Separately scoped acceptance decisions

| Dimension | Status | Basis |
|---|---|---|
| Evidence Integrity | **BLOCKED** | Synthetic validator passes; no post-8.2B genuine native-to-HTTP causal mapping |
| Budget Reconciliation | **BLOCKED** | Controlled proxy lifecycle & offline ledger pass tests; new native real-request/cost attribution not proven |
| Cross-platform Contract | **PASS (synthetic-only)** | Hermes, DSH and third independent normalized fixtures |
| Native E2E Regression | **BLOCKED** | 8.2B instrumented native runs not repeated |
| Privacy & Dependency Audit | **PASS (source/fixture scope)** | Sanitizer and Apache-2.0 source checks passed; no JevAny assets copied |
| Active Readiness | **NOT_AUTHORIZED** | Unchanged by Phase 8.2B |

Do not aggregate statuses to a single project PASS.

## 13. Next engineering actions

1. Validate the full clean candidate and public sanitizer; publish only
   after the review bundle passes.
2. Add platform-native **private** exporter link from real native event to
   the actual decision request ID, then produce new bounded Hermes and DSH
   OFF/Shadow healthy/Runtime-down native test runs.
3. Reconcile provider-proxy physical attempt records with platform-reported
   API calls, preserving unsupported and unknown usage and spend states.
4. Verify observation overhead with representative repetitions before
   discussing any speed/cost improvement.
5. Keep any Active/Canary expansion outside this phase.
