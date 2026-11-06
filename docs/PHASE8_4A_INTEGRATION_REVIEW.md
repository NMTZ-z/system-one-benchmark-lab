# Phase 8.4A — research integration review

Snapshot: 2026-11-06. GitHub main was
`062d52e753e7e00d91a536dc81e9d85b8819cb12`. This integration candidate
incorporates the frozen heads of #9–#13 in their dependency order, then #14.
The original Git commits and their authors remain ancestors. It is a Draft
candidate for review; no formal mainline merge is authorized by this document.

## Disposition and prior evidence

The figures below are historical reports from the respective PRs, not tests
rerun by the integration candidate. Mock/synthetic evidence is scoped to the
stated experiment and does not establish actual user value.

| PR | Decision for candidate | Historical checks reported at that stage |
|---|---|---|
| [#9](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/9) | Retain opportunity contract, synthetic value research, offline native diagnostics and HMAC-only Retry correlation. Exclude the opportunity module from the product wheel/sdist and source export. | Final stock-shell report: Python 1429 pass / 2 skip plus 5 separately run process checks; DSH 64, typecheck/build pass. Earlier frozen scopes and counts remain in the report. |
| [#10](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/10) | Retain the native stock-shell synthetic-main-provider protocol, verification and results as research. | Four-case scoped matrix; Python 1457 pass / 2 skip plus 5 process and 1 registry checks; DSH 64, typecheck/build pass. |
| [#11](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/11) | Retain H4D offline readiness, real-value feasibility tools and bounded evidence. | Python 1483 pass / 2 skip; 5 process and 1 registry checks; DSH 64, typecheck/build pass. Real H4D remained blocked. |
| [#12](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/12) | Retain H4D auth research and its explicit H4D-only changes to `scripts/phase8_2a_provider_cap.py`. Keep this proxy and its ledger exception out of the product export. | Python 1505 pass / 2 skip with 7 separate OS/process and 1 registry checks; DSH 64, typecheck/build pass. One private-ledger fixture remained unavailable. |
| [#13](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/13) | Retain H4E source, tests and sanitized evidence for research only; no automatic H4E execution or product installation path. | Python 1641 pass / 10 skip; 8 native H4E and 1 H4D auth test reported separately; DSH 64 previously passed. Nine-case synthetic rehearsal did not authorize real execution. |
| [#14](https://github.com/NMTZ-z/system-one-benchmark-lab/pull/14) | Retain product scope, versions and 8.4B handoff. Update the earlier archive-only decision and candidate baseline to match this integration. | Python 89 and DSH 64 passed; isolated Hermes validation and a clean 221-file source export passed on #14's own commit. Those numbers do not attest to this integration head. |

The complete head/base map, file groups and historical evidence links are in
[the archive index](PHASE8_3_ARCHIVE_INDEX.md). The later local-only H4E
closeout is newer than #13; its actual real-Provider E2E remains blocked.

## Findings and boundaries

1. **Distribution:** #9's `local_system_one/decision_opportunity.py` otherwise
   becomes part of a normal wheel, and the former public source allowlist
   includes H4 research executors. The default product allowlist and
   wheel/sdist exclusions keep them out while retaining the full source in
   GitHub and in the explicitly selected research archive.
2. **Frozen-input limitation:** the research classifier can raise `TypeError`
   for unhashable values in enum fields. This is reproducible with malformed
   offline input. The module and evaluator are included in the preregistered
   holdout hash set; altering them would invalidate the historical source
   verification. Defer a separately versioned fix, keep the original bytes and
   exclude them from product installation.
3. **Budget and process helpers:** #12's shared experimental proxy can use a
   narrowly identified historical owner ledger and #13 adds H4E-specific
   process and transport cases. These are not called by Runtime installation,
   import or startup; the H4 scripts are explicitly outside the product source
   export. The H4E controller itself lacks a kernel-enforced no-egress policy;
   its frozen report records that constraint. Their existence does not grant
   permission to use them.
4. **Normal tests:** the full repository's default pytest discovery includes
   historical experiment tests. H4E native tests require explicit source and
   interpreter settings, while some isolated sandbox/process tests can run by
   default. Use the product test selection for product checks; do not claim the
   full historical matrix passed unless it was actually run.
5. **Hermes:** #9 changes only the opt-in isolated-test HMAC Retry evidence
   hook. Current plugin defaults remain OFF; switching to Shadow with current
   defaults still enables four Gates. Search-only first Shadow is 8.4B work.
   The plugin still declares `0.9.0` although its candidate bytes differ from
   main's `0.9.0`; identify this development source by commit, not version
   alone. The planned `0.10.0` remains a future release.
   The earlier validator also warned about optional private Hermes Kanban
   imports, which require future compatibility review.

## Product distribution

- `release/product-files.txt` is the default source-export list. It contains
  the five Runtime Gate implementations, their HTTP service, MCP proxy,
  existing Hermes/DSH sources, contracts, user-facing scripts, selected tests,
  and the release/handoff documentation. It excludes H4 and Phase 8.3
  experiment programs and the frozen Opportunity classifier.
- `release/public-files.txt` remains the explicit full research-source export;
  it includes sanitized historical scripts, reports, fixtures and results.
  Both exports use the same sanitizer and each generates its own file manifest.
- The Python wheel and sdist exclude the frozen Opportunity classifier. The
  existing `model_backends/` research module remains for backward
  compatibility; the normal Runtime does not activate remote Providers.
- Neither source export includes private/raw Agent evidence or model weights.
  Final v0.2.0 component SHAs, artifact hashes, model license verification and
  full clean installation acceptance remain pending.

## Integration checks

- 312 focused Python tests passed on the candidate, including the historical
  frozen holdout checks, adapter contracts, the isolated Retry correlation
  hook, budget-proxy mock tests and synthetic authorization-boundary unit tests.
  No H4 execution matrix or real Provider was run. Two integration-specific
  test failures were fixed: a test now imports its verifier without depending
  on collection order, and the 8.2A provenance test permits the exact Hermes
  README change while keeping operational-source checks intact.
- The product source export's own default pytest selection passed 200 tests.
  Its wheel and sdist were built independently, contain all five Gate modules,
  and exclude `decision_opportunity.py` and experiment scripts. Builds from
  the full candidate and the product source export produced identical wheel
  and sdist hashes. A fresh Python 3.12 environment installed the wheel
  without dependencies, imported the Runtime outside the checkout and showed
  CLI help. This is not a full dependency installation or model inference.
- DSH typecheck, build and 64 unit tests passed. The installed Hermes source's
  isolated admission validator passed and reported the private Kanban API
  warning described above.
- Full-repository pytest collection found 1652 tests, including research and
  H4 tests. Collection did not execute them; the full suite was not run.
- Clean product/research export and hash verification must refer to the final
  candidate SHA published with the Draft PR. The earlier 221-file #14 export
  is not evidence for the integrated source.

## Standards review

No repository-specific coding standard violation was identified. Two findings
were reported: the frozen classifier's malformed-enum error is deferred, and
the research module's inclusion in the Runtime wheel is addressed by the
distribution exclusions.

## Spec review

Two distribution gaps were identified: the research module entered the wheel,
and the default source export included experimental executors. The candidate
separates both product artifacts and research source while retaining ancestry.
H4 controller and legacy owner-ledger constraints remain documented research
limits, not product capabilities.

Independent review: Standards 2 findings (one deferred, one addressed); Spec
2 findings (both addressed). The highest remaining risk is unauthorized use
of retained historical H4 tooling.

## Mainline merge and 8.4B

Review the result of each legacy PR and this integration diff first. If the
maintainer later approves this candidate, use a **merge commit preserving
ancestry**, not a squash or rebase merge. The preregistered holdout verifier
requires its original freeze commit `1245a3cb17120f0f6bee198a34aa159ea3eeb851`
to be an ancestor of HEAD; rewriting that history would break verification.
The exact final candidate SHA is recorded in the integration PR and its
generated release metadata, avoiding a self-referential commit SHA in source.

8.4B can start in a separate worktree from that exact reviewed integration
head while the PR remains Draft. Formal merge, production deployment,
Active/Canary and real Provider experiments require separate authorization.
