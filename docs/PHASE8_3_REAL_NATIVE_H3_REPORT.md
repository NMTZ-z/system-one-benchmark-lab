# Phase 8.3A — Real Hermes H3 Runtime-down / Shadow fail-open

**Executed 2026-10-21. Scoped native and fail-open acceptance: PASS.
Entire Phase 8.3A real Provider acceptance: BLOCKED by original H1
unresolved request and incomplete Provider-level usage attribution.
This is a real StepFun native Agent task, not Mock.**

## 1. Frozen identity and what was actually run

- Frozen BEFORE the H3 Provider traffic: source commit
  40a7b4416db07e6eedcf505131e0c9b3e1a98eac, including the
  [H3 preregistration](PHASE8_3_REAL_H3_PREREGISTRATION.md), safety
  rules, native runner and full pre-run offline regression.
- Platform: Hermes v0.22.1 in the dedicated nonproduction test Home.
- Main model: actual StepFun Step Plan step-5-preview behind the fixed
  localhost physically capped HTTP outlet. No new pay-as-you-go API.
- System One: plugin Shadow, no Active or Canary authority. The Laya
  Runtime was intentionally NOT running on 127.0.0.1:18782.
- Observer: a separate localhost 18793 process forwarded Completion
  observations to the absent Runtime, recording true HTTP 503 responses.
  No local Laya MLX inference ran during this H3 outage test.
- Task: exactly one native read_file of a new randomly generated
  hidden private original file. Its contents were absent from the
  Agent prompt. No shell, browser, write or network tool task was
  authorized; the original file stayed byte-for-byte unchanged.
- Native task completed normally in **13.632 seconds**, exit code 0.
  The native Hermes file/tool-result identity, original file bytes,
  final Agent response and Session completion were independently
  checked from isolated SQLite and private input.

**Native task verdict: PASS_SCOPED.** This is one engineered native
read-only task, not an estimate of production task success.

## 2. Real Runtime failure and independently linked evidence

| H3 controlled observation | Actual evidence |
|---|---|
| Laya Runtime listening | NO, intentionally down |
| Native Completion/Observer events | 2 |
| Observer HTTP statuses | **503, 503** |
| Runtime/decision backend | null, null |
| Plugin event action status | **failed_open, failed_open** |
| Native↔Adapter↔HTTP exact keyed links | **2 of 2 PASS** |
| Native task final and independent file oracle | **PASS** |
| Any System One task stopping / auto retry / model switch | **NONE** |
| Test Home restored to OFF and test services shut down | **YES** |

The native/Adapter/HTTP correlation is based on the original Hermes
SQLite tool/session identity and the test-only keyed request refs,
not on timestamp proximity. HTTP 503 has no valid echoed successful
model request ID; the verifier checks an exact causal *request* link,
without inventing a successful response match.

**Engineering conclusion:** When the decision Runtime was
intentionally unavailable, the real Hermes Agent could still
complete this read-only native task, and Shadow recorded two
strictly correlated failed-open events. This is credible one-case
reversibility/fail-open evidence. It does not establish fail-open
behavior for every error category or general Agent workload.

## 3. Original physical StepFun Provider ledger remained append-only

H3 used the SAME physical Provider ledger as H1 and H2, never reset or
refunded. H1 and H2 evidence is independently frozen in earlier
privacy-restricted snapshots. H3 original ledger SHA-256:

5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb

| Physical Provider count | H1 OFF | H2 healthy Shadow | H3 Runtime-down |
|---|---:|---:|---:|
| Reserved and attempted | 3 | 3 | **2** |
| Genuine upstream HTTP 200 | 2 | 3 | **2** |
| No terminal outcome observed | **1** | 0 | 0 |
| Durable proxy result records | 2 | 3 | **2** |
| Native Hermes self-reported main-model calls | 2 | 2 | **2** |
| Physical requests beyond those reported main calls | 1 | 1 | **0** |

**Global physical requests: 8/24**, in slots 1–8. H3 alone had two
actual requests, two terminal HTTP 200 results, zero new transport
unknowns and no physical-vs-main call discrepancy.

The historic H1 slot 1 is STILL attempted and unfinalized. Its actual
upstream execution, billing status and ultimate outcome cannot be
reconstructed or legitimately backfilled. The global historical
budget integrity therefore remains BLOCKED even though both H2 and
H3 have fully finalized new transports.

Hermes self-reported H3 input 7,244 tokens and output 92 tokens.
These figures are not independently Provider-billed tokens. Actual
StepFun Plan credits, monetary cost, token saving and overhead impact
remain **UNKNOWN / NOT MEASURED**.

The nominal 16 unreserved slots out of the original cap do not
authorize further Provider tests while the historic unknown is a
blocker.

## 4. Background title generation: a strong, still unproven explanation

Inspection of the actually installed Hermes source established:

1. By default, a new native session starts a concurrent asynchronous
   model-backed title upgrade.
2. The one-shot CLI waits at most 10 seconds for its title thread.
   Such a background Provider request can remain in flight after
   the foreground Agent finishes.
3. H1 and H2 retained default title-model-upgrade settings. Both
   generated three physical requests but reported two main-model
   calls, with zero completed auxiliary calls in the native usage.
4. H2's first original proxy request lasted about 33.13 s, while
   its native Agent finished after 29.581 s.
5. H3 disabled ONLY the new test Home's title model upgrade, retaining
   the non-LLM derived title. The physical Provider count changed to
   two, matching its two reported main-model calls.

Together, the source mechanism and before/after operational counts
**strongly support** the background title LLM as the extra call
source. However H3 also differs by task/runtime failure condition,
and the original Provider ledger has no request-role header, title
call ID or independently verified Provider-side usage record.
We therefore **cannot uniquely assign H1/H2 physical slot 1 or 4
to title generation**, claim a causal controlled experiment, or
retroactively classify the unknown request as free.

Practical mitigation: keep the background model title upgrade
disabled ONLY in the isolated research Home and account ALL
physical requests at the local outbound proxy irrespective of
the Agent's logical usage. No owner/production Hermes settings
were changed.

## 5. Independent evidence, regression and limits

The new independent, read-only adjudicator
(scripts/phase8_3_verify_real_h3.py) verified the frozen H3 run,
private native SQLite/file oracle, actual HTTP 503 observer records,
two test-only HMAC causal links and appended physical request ledger.
It produced an allowlisted public JSON aggregate:

results/processed/phase8_3_h3_real_stepfun_runtime_down.json

The original test-only H3 Adapter and H1+H2+H3 ledger snapshots
are kept under Git-ignored private storage for later audits. H2's
historical verifier was also updated to select only H2's two
frozen HMAC request references, so later H3 Adapter events cannot
silently poison or replace previously verified H2 evidence.

A further regression verifies that duplicate, missing, forged or
incorrectly attributed native/Adapter/Provider evidence is rejected.
All new contract and fake-provider tests are **offline only**;
they do not authorize, initiate or replay real StepFun requests.

This report is authored AFTER the real H3 run. It must never be
mistaken for the preregistered native execution commit.

**Post-run code-quality verification:** Python full suite
**1151/1151 PASS**; DSH Vitest **64/64 PASS**; TypeScript typecheck
and DSH build PASS. The public release privacy-scan preview
PASSED and included 274 allowlisted files. The final clean-Git
source and publish-ready manifest must be revalidated on the
separate report commit before declaring publication complete.

**Historical replay hardening:** H1 original first-ten Provider
events were separately snapshot-preserved under private storage
using their already-published SHA-256. H2's original first 22
events and H3's first 30 remain separately hash-frozen. H1, H2
and H3 are now each independently reread and rescored after
later event appends. This was a post-run verifier correction,
not an alteration of any of the 8 actual Provider attempts.

## 6. Decision

| Acceptance question | Result |
|---|---|
| H1 native OFF task | PASS_SCOPED; transport history BLOCKED |
| H2 genuine local Laya/MLX Shadow | PASS_SCOPED; billing attribution partial |
| H3 real Runtime-down / fail-open | **PASS_SCOPED** |
| H3 physical request lifecycle | **2/2 terminal HTTP 200** |
| H3 source of possible extra background request | No extra observed; H1/H2 cause still inferential |
| H4 real native failed-read | NOT RUN |
| DSH real native D1–D4 | NOT RUN |
| Historical Phase 8.3A global budget integrity | **BLOCKED_HISTORICAL_H1_UNRESOLVED** |
| Real-world Agent time, token and billing savings | NOT ESTABLISHED |
| Production Canary/Active readiness | **NOT AUTHORIZED** |

No H3 rerun, new paid Provider test, production Agent configuration
change, GitHub main merge or NAS main change is justified by this
scoped result. PR #9 remains Draft pending explicit later acceptance
and stronger real-world evidence.
