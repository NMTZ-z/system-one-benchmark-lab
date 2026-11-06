# Phase 8.3 — research archive index

Phase 8.3 is **CLOSED_LIMITED**. The 8.4A integration candidate retains the
frozen research source and commit ancestry of PRs #9–#13, plus the release
baseline from #14. At the 2026-11-06 audit, the candidate and all six
original PRs were Draft and unmerged; check GitHub for their current status.

The code and sanitized evidence are available for study in the candidate.
H4D/H4E programs remain historical research tools: keeping source does not
authorize running them. The product source bundle and Runtime wheel exclude
the Phase 8.3 opportunity module and H4 experiment programs.

| PR | Frozen base → head | Research retained in candidate |
|---|---|---|
| [#9](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/9) | `062d52e753e7e00d91a536dc81e9d85b8819cb12` → `f2392667e722f13c2dc35c4ffae08e36f963c6b4` | Opportunity contract, value replay, historical native diagnostics, tests and reports. |
| [#10](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/10) | #9 → `e971889e23ecae6db54712c43772eb670c0a068d` | Scoped stock-shell four-case offline evidence. |
| [#11](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/11) | #10 → `da1761879ca2425306a78c4252a1604bc2ad820b` | H4D offline readiness and evidence-feasibility research. |
| [#12](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/12) | #11 → `2c76bd4d705c8552e9c1a5105ce003e7e8f7586f` | H4D credential compatibility and its narrowly scoped shared budget-helper changes. |
| [#13](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/13) | #12 → `b0ea294ab74f35b99e780eaf29aab2b36d205168` | H4E offline rehearsal, process-control and frozen evidence. |

All were open, Draft and unmerged when rechecked on 2026-11-06. The PRs are
stacked; integrating them individually later without reconciling their shared
history can duplicate work or reintroduce conflicting README/release changes.
The integration preserves their original commits as ancestors and requires
maintainer approval before formal mainline merge. When their head commits
reach their respective bases through another PR, GitHub may mark the original
PRs as merged indirectly.
The [complete pre-integration README](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/b0ea294ab74f35b99e780eaf29aab2b36d205168/README.md)
remains available at the frozen #13 commit; the product-facing README links
here to keep first-run guidance concise.

## Source, product and evidence boundaries

| Source group | Disposition and dependency |
|---|---|
| `local_system_one/workflows/*.py`, `runtime/*.py`, `service.py`, Hermes/DSH adapters and `contracts/adapter-contract-v1.schema.json` | Existing product implementation. #9 adds a test-only HMAC Retry correlation hook to Hermes; no new Gate or production authority. |
| `local_system_one/{evidence_integrity,budget_observability}.py` | Existing reusable 8.2B formats; they do not grant execution authority or prove real billing. |
| `local_system_one/decision_opportunity.py`, `benchmarks/decision_value/`, associated tests and processed results | Kept as frozen research source. The classifier depends on `evidence_integrity.py` and is not imported by the Runtime path. It is excluded from the product bundle, wheel and sdist. |
| `scripts/phase8_2a_native_run.py`, `scripts/phase8_3_prepare_shared_dependency_home.py`, `scripts/phase8_3_native_rehearsal.py` and #10 stock verifier | Research harnesses depend on isolated homes, fixtures and an explicitly chosen test environment; none is in the product source bundle. |
| `scripts/phase8_2a_provider_cap.py`, `scripts/phase8_3_transport_closeout.py` and `scripts/phase8_3_h4d_*.py` | #12 adds an H4D-only owner-ledger exception, fixed digest, run ID, port and caps to the shared **experimental** proxy. It is not a Runtime dependency or product installer. These historic scripts must not be treated as authorization to touch the original ledger or call a Provider. |
| `scripts/phase8_3_h4e_*.py`, `scripts/phase8_3_h4b_*.py`, related tests, reports and processed evidence | Retained for research, with H4E-specific process ownership, proxy, admission and recovery dependencies. Excluded from the product bundle and never automatically started. |

The frozen opportunity classifier can raise `TypeError` for a list or object
in certain enum fields. It is an offline input-validation limitation, not an
execution-authority bypass. Its bytes are part of the preregistered holdout
hashes; editing it would invalidate that historical source check. Fix a
separately versioned research implementation when it is next needed, retaining
the original evidence and hashes.

## Evidence and limits

- [#9 final report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/f2392667e722f13c2dc35c4ffae08e36f963c6b4/docs/PHASE8_3_FINAL_REPORT.md)
  and [opportunity contract](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/f2392667e722f13c2dc35c4ffae08e36f963c6b4/docs/PHASE8_3_OPPORTUNITY_CONTRACT.md).
- [#10 stock-shell report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/e971889e23ecae6db54712c43772eb670c0a068d/docs/PHASE8_3_NATIVE_STOCK_SHADOW_REPORT.md):
  bounded synthetic-main-provider evidence, not measured real-world savings.
- [#11 H4D readiness](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/da1761879ca2425306a78c4252a1604bc2ad820b/docs/PHASE8_3_H4D_ADMISSION_REAL_INTAKE_REPORT.md),
  [#12 authentication report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/2c76bd4d705c8552e9c1a5105ce003e7e8f7586f/docs/PHASE8_3_H4D_AUTH_COMPATIBILITY_REPORT.md),
  [#13 H4E parity report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/b0ea294ab74f35b99e780eaf29aab2b36d205168/docs/PHASE8_3_H4E_PARITY.md).
- A later local-only closeout dated 2026-11-05 reports one H4E attempt at
  `512cfdb6791a400a5d588431a5fadf15fc483b90` blocked on DNS before the real
  Agent and Provider proxy started. It records zero new physical Provider
  requests, the historical 8/24 ledger and one H1 UNKNOWN. That later source
  and private raw evidence are not included in PR #13; do not reinterpret its
  earlier statements as a current real-E2E result.

Public code and sanitized reports are indexed. Completeness of all private raw
evidence has not been re-audited; archive coverage remains **PARTIAL**. Actual
real Agent value and savings are not established.
