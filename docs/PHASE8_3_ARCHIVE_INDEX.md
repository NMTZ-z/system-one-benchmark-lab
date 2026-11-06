# Phase 8.3 — archive and extraction index

Phase 8.3 is **CLOSED_LIMITED**. Keep the following open Draft PRs and their
frozen source/report references intact. This index preserves pointers, not a
new claim that every private raw record has been re-audited: archive coverage
is **PARTIAL**. H4E is deferred and does not block 8.4B.

| PR | Actual base → head on 2026-11-05 | Delta | Disposition |
|---|---|---:|---|
| [#9](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/9) | `main@062d52e753e7e00d91a536dc81e9d85b8819cb12` → `feat/phase8-3-decision-value@f2392667e722f13c2dc35c4ffae08e36f963c6b4` | 132 files | Selective future extraction only; archive research and test harness. |
| [#10](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/10) | #9 head → `feat/phase8-3-native-stock-shadow@e971889e23ecae6db54712c43772eb670c0a068d` | 12 files | Archive scoped native stock-shell proof and its fixtures. |
| [#11](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/11) | #10 head → `feat/phase8-3-h4d-admission-value-intake@da1761879ca2425306a78c4252a1604bc2ad820b` | 10 files | Archive H4D readiness and evidence-feasibility study. |
| [#12](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/12) | #11 head → `feat/phase8-3-h4d-once-step-plan@2c76bd4d705c8552e9c1a5105ce003e7e8f7586f` | 24 files | Archive H4D-specific auth, ledger and process changes. |
| [#13](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/13) | #12 head → `feat/phase8-3-h4e-admission@b0ea294ab74f35b99e780eaf29aab2b36d205168` | 54 files | Archive H4E offline rehearsal; defer future work. |

All five were open, Draft and unmerged at this snapshot. Later PRs inherit
earlier changes. GitHub reporting a clean merge does not establish that the
whole stack belongs in the product. The legacy branches also modify
`README.md` and `release/public-files.txt`, which 8.4A changes; a future
merge or rebase can create textual and semantic conflicts.

## File-level disposition

Paths below refer to the frozen PR commits unless explicitly described as main.
Each grouping reflects implementation and dependencies, not filename alone.

| Classification | Files and dependencies | Reason |
|---|---|---|
| **KEEP_IN_MAIN** | `local_system_one/workflows/*.py`, `service.py`, `runtime/{mlx,ane,sources}.py`; Hermes `__init__.py` and `plugin.yaml`; DSH `src/{index,policy,retry}.ts`; `contracts/adapter-contract-v1.schema.json` | Existing product Gate, adapter, runtime and contract paths. They have distinct feature and evidence limits in the [baseline](PHASE8_4A_RELEASE_BASELINE.md). |
| **KEEP_IN_MAIN** | `local_system_one/{evidence_integrity,budget_observability}.py`, `docs/PHASE8_2B_{EVIDENCE_CONTRACT,BUDGET_LEDGER}.md`, associated synthetic fixtures and verifier | Reusable evidence/budget formats, not permission to execute or proof of actual bills. |
| **SELECTIVE_EXTRACT** | #9 `local_system_one/decision_opportunity.py`, `docs/PHASE8_3_OPPORTUNITY_CONTRACT.md`, `tests/test_phase8_3_opportunity.py`; depends on main `evidence_integrity.py` | Useful finite-choice classification with Shadow-only authority and validated labels. Its provenance and policy claims still need independent verification. 8.4B does not need it; keep the original credited commit as source for a future focused PR. |
| **SELECTIVE_EXTRACT** | #9 Hermes `__init__.py` additions and `tests/test_retry_hermes.py`; depends on existing `_private_evidence_refs` and isolated-test HMAC opt-in | Adds Retry test-only provenance and request matching; it is not a general runtime safety fix. Extract only if a future product evidence requirement justifies it. |
| **SELECTIVE_EXTRACT** | #9 `scripts/phase8_3_h4b_owned_processes.py` and tests; #13 changes add `phase8_3_h4e_process_identity.py` and case-specific recovery | Identity-before-signal and fail-closed cleanup are useful patterns. Current code depends on H4 private ledgers, case IDs and process-controller modules; do not transplant it into first-run as a generic library without redesign and independent tests. |
| **ARCHIVE_ONLY** | #9 `benchmarks/decision_value/{capture,evaluate}.py`, `holdout_v1/*`, fixture JSONL and `results/processed/phase8_3_decision_value.json` | Synthetic/public-reconstruction replay and reports are useful research; they do not prove native task value and are not needed by the product. They depend on the opportunity contract and fixture-specific policy logic. |
| **ARCHIVE_ONLY** | #9 `scripts/phase8_2a_native_run.py` changes and `scripts/phase8_3_{prepare_shared_dependency_home,native_rehearsal,init_diagnostic}*.py`; #10 `phase8_3_verify_stock_shadow.py` and related tests/reports | Isolated native test homes, auth routing, simulated Provider and precommitted task evidence. #9's shared script imports its 8.3 home preparation; copying it alone would break main's existing helper. |
| **ARCHIVE_ONLY** | #11 `scripts/phase8_3_h4d_readiness.py`, `phase8_3_real_value_intake.py`, their tests and `docs/PHASE8_3_H4D_ADMISSION_REAL_INTAKE_REPORT.md` | H4D-specific admission and feasibility conclusions; preserve links as historical evidence. |
| **ARCHIVE_ONLY** | #12 `scripts/phase8_2a_provider_cap.py` delta and `phase8_3_h4d_direct_child.py`, `phase8_3_transport_closeout.py`, auth tests/report | The shared budget proxy gains an H4D-only ledger-path exception, fixed ledger digest, run ID, caps and port; it imports the 8.3 closeout auditor. Merging it would couple the common helper to one historical experiment. Auth compatibility is likewise tied to the pinned Hermes path. |
| **ARCHIVE_ONLY** | #13 `scripts/phase8_3_h4e_{controller,proxy,runner,rehearsal,adjudicate,sdk_guard,source}.py`, related contract, process identity, tests and reports | Dedicated H4E execution, proxy, Seatbelt, process identity and recovery machinery. Changes to shared H4 helpers also carry H4E cases and dependencies. |
| **DEFER** | H4E real execution and repairs; real-provider value and billing claims; optional Luna Decisions API | No real H4E restart or Provider request in 8.4A/8.4B. Luna may be separately researched in 8.4C and cannot be required for local use. |

For any approved future extraction, retain original author and source commit,
bring only the necessary dependencies, review the diff from current main, and
run independent tests. Do not retarget #13 to main or close, delete or merge
the historical PRs as a shortcut.

## Evidence pointers and limits

- [#9 final report at its frozen head](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/f2392667e722f13c2dc35c4ffae08e36f963c6b4/docs/PHASE8_3_FINAL_REPORT.md)
  and [opportunity contract](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/f2392667e722f13c2dc35c4ffae08e36f963c6b4/docs/PHASE8_3_OPPORTUNITY_CONTRACT.md).
- [#10 four-case stock-shell report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/e971889e23ecae6db54712c43772eb670c0a068d/docs/PHASE8_3_NATIVE_STOCK_SHADOW_REPORT.md):
  bounded synthetic-main-provider evidence, not measured real-world savings.
- [#11 H4D readiness report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/da1761879ca2425306a78c4252a1604bc2ad820b/docs/PHASE8_3_H4D_ADMISSION_REAL_INTAKE_REPORT.md);
  [#12 auth report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/2c76bd4d705c8552e9c1a5105ce003e7e8f7586f/docs/PHASE8_3_H4D_AUTH_COMPATIBILITY_REPORT.md);
  [#13 H4E parity report](https://github.com/NMTZ-z/system-one-benchmark-lab/blob/b0ea294ab74f35b99e780eaf29aab2b36d205168/docs/PHASE8_3_H4E_PARITY.md).
- Historical ledger state reported by the frozen evidence: 8/24 physical
  reservations, one H1 outcome UNKNOWN. This index does not fabricate its
  missing result or treat a compatible reproduced failure as its unique cause.
