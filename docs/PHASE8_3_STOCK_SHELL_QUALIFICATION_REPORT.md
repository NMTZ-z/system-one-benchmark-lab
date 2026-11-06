# Phase 8.3A — frozen Hermes stock-shell OFF native closeout

**Executed: 2026-10-26 (local). Engineering result: `PASS_OFFLINE_NATIVE_REHEARSAL`, limited to a real Hermes native Agent/tool with a synthetic main Provider.** Real H4D StepFun and DSH native paid E2E remain NOT RUN; Active/Canary remains NOT AUTHORIZED. This is a distinct fifth, opt-in case and does not amend H1–H4C originals.

## Immutable input and local experiment

| Scope | Verified fact |
|---|---|
| Original public PR branch checked at kickoff | `840ea824d23c2bd980e44035556efc4ad48194f4` |
| New separate local worktree/branch | `audit/phase8-3-closeout-20261025`; NAS `main` and former 8.3 worktree unchanged |
| Preregistered implementation/protocol Git freeze | `da998de1601155f7f2bc47185768dea612b0642a` |
| Official Hermes upstream source | Git archive at `4d04303818b61bf3aa09278af48356315515965b`; six source file hashes pinned and verified |
| Model transport | Exactly two bounded `httpx.MockTransport` fixture completions in-process; zero actual StepFun requests |
| Native tool | Unmodified Hermes `read_file`, real filesystem missing-file error, normal dispatcher, lifecycle hooks and SQLite persistence |
| Shell dependency | Unmodified `LocalEnvironment.init_session` and `ShellFileOperations._exec`, 3 genuine Bash spawns (login + nonlogin), 5 fixed upstream ancillary process probes |
| Isolation | New credential-empty HOME; macOS Seatbelt denied outside scratch reads/writes and all network; child process audit constrained to expected upstream programs |
| End-to-end observation | Exactly one original missing-file tool call/result with matching IDs; OFF mode, zero Shadow HTTP observations; no second tool, automatic retry or Active action |
| Independent adjudication | `PASS_OFFLINE_NATIVE_REHEARSAL` on frozen execution and a later separate-process `--verify` read-only recheck; zero issues |
| Recovery | All owned child groups stopped and independent disposable SQLite/Home restoration and sentinel checks passed |

The upstream archive is not the installed production checkout. It contains no
credential files. The public source audit pins the six relevant original files;
it is **not** a full Git-tree cryptographic attestation. Raw file paths, native
messages, database Session IDs, sandbox logs and correlation keys remain only
in private ignored experiment artifacts, never in public release.

New public bounded evidence: [`results/processed/phase8_3_stock_shell_qualification.json`](../results/processed/phase8_3_stock_shell_qualification.json).
The original safety preregistration is separate:
[`PHASE8_3_STOCK_SHELL_QUALIFICATION.md`](PHASE8_3_STOCK_SHELL_QUALIFICATION.md).

## Regression and independent safety assessment

The source/benchmark code was frozen and clean **before** the native case.
The successful native case and its independent verifier did not dirty the
worktree. Following that case, the latest validation included:

- **Python full isolated regression: 1,429 PASS / 2 SKIP / 5 deliberately deselected** under an external private temporary root, an OS sandbox allowing only localhost fixture sockets, no external network, and no production writes. Both SKIPs are explicit optional evidence dependencies: original private Provider-ledger fixture is intentionally unmounted; the native registry integration requires an exported Hermes source. The latter was subsequently tested separately using the pinned, credential-free upstream export and **PASS (1/1)**.
- **Five OS/process-specific regressions: 5/5 PASS in separate isolated processes**, including actual macOS Seatbelt tests and the safety of terminating only child process groups created for a test. These cannot run nested beneath the outer test Seatbelt, which blocks such signals. These five are exactly the five deselections above. Therefore the original complete test collection had no untested mandatory case; one historical private-ledger fixture remains SKIP.
- **DSH: 64/64 Vitest PASS**, TypeScript typecheck PASS, build PASS. Packages were installed to an isolated, disposable dependency directory from the committed lockfile; production DSH and system-global packages were not changed. macOS test sandbox logged harmless worker-teardown `EPERM` notices, with no lingering test process detected.
- **Test harness qualification:** the first Python regression attempt used scratch underneath repository `private/`; that invalidated a fixture's "outside repository" precondition. It was corrected by creating a fresh user-owned temporary root outside the worktree. Another deliberately strict outer OS sandbox refused locally created process-group termination. Those environmental failures were not reclassified as passing tests: separate reproduction with properly isolated inputs passed. No production preflight rule or authorization boundary was weakened.
- **Historical StepFun physical ledger** independently SHA-256 checked, unchanged at `5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`. Existing 8/24 physical attempts and the original one H1 UNKNOWN remain; nominal unspent slots are not new authorization.

Scope limits: This closes the **original shell transport dependency
compatibility gap in a bounded OFF test**. It does **not** establish real
StepFun missing-file behavior, real Retry Shadow model inference, DSH real
Provider E2E, Agent task improvement, token savings, or provider billing.
The decision is to keep the complete 8.3A real Provider qualification
**PARTIAL / globally BLOCKED**, not to approve H4D or Active. PR #9 remains
Draft for review; do not automatically merge.
