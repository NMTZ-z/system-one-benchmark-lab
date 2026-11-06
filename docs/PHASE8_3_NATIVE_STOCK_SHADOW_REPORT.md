# Phase 8.3A supplement — stock Hermes native file-failure Shadow E2E

**Execution: 2026-10-26. Result: `PASS_SCOPED` on four zero-paid native
Hermes experiments. Not real main-Provider E2E. Not Active readiness.**

This experiment closes a specific technical gap: the existing offline
four-case native rehearsal mocked two shell-dependent file lookup calls.
The new opt-in stock-shell cases run **unmodified upstream Hermes Bash
initialization and shell file operations** with a genuine `AIAgent`, native
`read_file`, tool dispatch, SQLite persistence, official lifecycle hooks and
unchanged local System One Adapter, while the **main-model responses remain
strictly synthetic via in-memory `httpx.MockTransport`**.

## Precommitted execution and history

- GitHub PR #9 parent: `f2392667e722f13c2dc35c4ffae08e36f963c6b4`.
  This work was isolated in `feat/phase8-3-native-stock-shadow`, not
  placed directly on `main` or the older PR branch.
- **Initial pre-execution freeze:** `c154446802e9433289c357342e24b3bd5c601068`.
  It produced **three PASS_SCOPED and one original BLOCKED**: the 503 case
  was wrongfully required by the independent *evaluation policy* to provide
  a normal `ask_user` Retry decision even though unavailable Runtime must
  produce **no decision** and failed-open observation. It was not reported
  as an experiment PASS and original evidence was not overwritten.
- **Adjudication correction and second pre-execution freeze:**
  `58a4d6b895e5da9e5848bf0a7a123eff32e56fc9`. See the
  [independent amendment](PHASE8_3_NATIVE_STOCK_SHADOW_AMENDMENT.md).
  Added negative tests for forged 503 decisions and wrong failure reasons;
  no production Gate policy or authority was changed.
- The second clean, frozen four-case matrix executed the unchanged official
  Hermes source `4d04303818b61bf3aa09278af48356315515965b` and pinned
  Laya snapshot `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`.
  Local model weights SHA-256 is
  `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e`.
  All execution logs, test Session IDs, HMAC secrets, target paths, raw
  native conversations and process receipts remain Git-ignored and private.

## Native and Shadow results, verified from original evidence

| Frozen case | Authentic missing `read_file` | Adapter→HTTP exact causal joins | Real Laya 421M local inference | Outcome |
|---|---:|---:|---:|---|
| `off_stock_shell` | 1 | 0 | 0 | PASS_SCOPED |
| `shadow_stock_fixture` | 1 | 3/3 | 0 (2 synthetic fixture predictions) | PASS_SCOPED |
| `shadow_stock_mlx` | 1 | 3/3 | **2 Completion**, warmup separately 1 | PASS_SCOPED |
| `shadow_stock_503` | 1 | 3/3 (HTTP 503) | 0 | PASS_SCOPED |

Each case launched three real upstream Bash children and five bounded
upstream environment helpers. The original Hermes `read_file` returned a
structured missing-file result in actual SQLite, with exact tool-call ID,
one original tool and two synthetic Provider fixture responses. **No native
tool was retried by System One.** All four native final-message digests
were byte-for-byte identical and the originally absent file stayed absent.

Healthy Shadow emitted two Completion decisions and one Retry observation
per case. In the actual MLX case there were **two successful local model
predictions**, not three: the Retry Gate was immediately resolved as
**`ask_user` / `retry_budget_unverified`** by its existing hard rule. The
Runtime-down case recorded three **failed-open** observations with **zero
invented decisions**. This correctly preserves native Hermes behavior
but does **not** prove that Laya can make better real Retry decisions.

The independent read-only verifier
[`scripts/phase8_3_verify_stock_shadow.py`](../scripts/phase8_3_verify_stock_shadow.py)
was run separately against source-frozen originals. It independently
cross-checked native SQLite, actual original tool error, stage/turn/Session
identity, independently recomputed HMACs, HTTP path/status and consumed
answers, model counters, process ownership/absence, original restored
Home/runtime trees and protected sentinel, and source/model SHA bindings.
Every case was re-adjudicated PASS_SCOPED; result totals were **9/9 causal
joins, 2 actual MLX Completion calls, 0 actual Retry calls, 0 external
Provider calls, 0 Auto/Canary actions**. A separate negative-test suite
rejects forged task success, tool/Session identity, wrong model evidence,
false Runtime-down decision or source provenance. See the
[privacy-safe aggregate](../results/processed/phase8_3_stock_shadow_four_case.json).

## Security, scope and limitations

- Native process uses macOS Seatbelt with read/write allowed only for the
  exact disposable experiment and pinned source/dependencies, no external
  egress and only the owned local HTTP port for Shadow. The new stock cases
  alone permit bounded upstream Bash subprocess creation; old default
  no-fork tests and production policies are unchanged. Each process is
  stopped with PID/PGID/UID/start-time ownership checks. Restorations and
  output target absence were independently verified.
- **Main Agent model is synthetic.** No new StepFun authentication or
  request, no Provider billing proof, no Native StepFun H4D, no DSH real
  Provider E2E and no real Agent task performance comparison occurred.
  MLX inference is real *local* computation; Shadow only observes and
  therefore cannot establish actual avoided model calls, tokens or time.
- The newly named stock-MLX case did not emit library-version fields in
  Runtime metrics. Independent source-model SHA, actual
  `local_system_one.runtime.mlx.MLXRuntime` class and measured two calls
  establish local model execution, not a complete runtime-dependency
  version provenance audit. Do not claim otherwise.
- Historical StepFun physical ledger SHA remained
  `5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`:
  **8/24 attempts; one original H1 outcome UNKNOWN**. It was not
  corrected, refunded, consumed or reclassified in this experiment.
- Active/Canary and real H4D **NOT AUTHORIZED**. See the
  [next-stage admission protocol](PHASE8_3_REAL_VALUE_FOLLOWUP_ADMISSION.md).

**Engineering decision:** technically qualify the offline native
stock-shell/Hermes Observer chain in these bounded synthetic-main tests;
continue holding real-Provider 8.3A qualification PARTIAL/BLOCKED,
real Laya incremental value NOT_ESTABLISHED and actual Agent savings
NOT_MEASURED.

## Final clean-code engineering regression and release QA

Executed on the separate branch after the frozen four-case matrix and
publication of the independent read-only verifier:

- **Python main suite:** `1457 PASS / 2 SKIP / 5 separately deselected`
  inside a macOS Seatbelt with only owned localhost test sockets, controlled
  subprocesses and disposable filesystem writes. One SKIP is the
  intentionally unmounted historical private Provider-ledger fixture;
  the other is the optional official Hermes source-registry test.
- **Separate OS/process tests:** `5/5 PASS`, including actual Seatbelt
  sensitive-file denial and identity-checked process-group teardown. These
  exact five are the main-suite deselections because nested Seatbelt
  would block signal tests rather than test their intended control.
- **Optional pinned upstream Hermes registry test:** separately `1/1 PASS`
  against a credential-free exported frozen source, without changing
  installed Hermes or production profiles.
- **DeepSeek Harness:** `64/64 Vitest PASS`; TypeScript typecheck PASS;
  TypeScript build PASS. Test dependencies were read from an independently
  isolated lockfile installation, with a temporary `node_modules` link
  removed afterward. Sandbox emitted worker-shutdown `EPERM` notices,
  but Vitest finished with exit status 0; this is not a real DSH E2E.
- **Public bundle:** `347` allowlisted files; sanitizer PASS;
  independently verified full SHA-256 manifest; `publish_ready=true`
  from the clean release commit. Only bounded aggregate, source, protocol,
  tests and reports are in the bundle; no raw native or credential records.

These results supersede neither the first historical experimental BLOCKED
verdict nor the original H1 UNKNOWN. They are the **offline engineering
qualification** for this separate stacked change, not approval to merge
PR #9, conduct paid tests, or activate any Gate.
