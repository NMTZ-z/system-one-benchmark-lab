# H4D credential compatibility — final engineering acceptance

Date: 2026-10-26. Repair base:
`a6936c77071bd150b1e378a5f0cc331b4df795dd` on
`feat/phase8-3-h4d-once-step-plan`, Draft PR #12.

**Engineering validation: PASS within the scope below. Real H4D E2E:
UNVERIFIED. H4D is consumed; no retry occurred. H4E: proposal prepared,
execution NO-GO and not authorized.** The source freeze and release
SHA-256 manifest are recorded in the clean release bundle and PR receipt.

## Failure and evidence limit

The preserved H4D log reports no usable StepFun credentials, before any
new physical Provider request. The preceding official authentication check
had reported READY outside the native child's restricted environment.

The real pinned Hermes resolver, synthetic profile credentials and the
original H4D Seatbelt policy reproduce this precise failure:

```text
load_pool → read_credential_pool → optional global auth store
  global_path.exists() → PermissionError
  outer credential resolver suppresses the exception → missing_api_key
```

Frozen `hermes_cli/auth.py:522` checks existence outside its unreadable-store
handler. The profile credential is readable and valid in the reproduction,
but the unrelated global-store metadata denial aborts resolution. This is
the demonstrated cause of the reproduced error. The original real run has
no internal traceback, so unique retrospective attribution remains
unproven. Its failed verdict and original evidence are preserved.

The three authentication source files match their Git objects at Hermes
`4d04303818b61bf3aa09278af48356315515965b`. Neither the archive nor installed
Hermes source was changed.

## Minimal repair and retained boundaries

Only the H4D child installs a process-local wrapper for the optional global
store. It converts `PermissionError` to an empty global store, matching the
official reader's documented behavior for an unreadable optional store.
Other wrapper exception types are preserved; profile failures still block.

The child then calls the real official runtime resolver and `load_pool`.
Admission requires one manual profile credential, StepFun identity,
`http://127.0.0.1:18794` for both pool and resolved route, a nonempty key,
and equality with that profile entry. It neither injects a replacement
key nor prints the key/underlying error. Failure emits a fixed blocked
message with the original exception chain suppressed.

The previous no-model `_run_agent` stub did not reach credential resolution.
The parent now requires `official_runtime_credentials_resolved: true` in
H4D's offline preflight before starting services or the Agent. H4B/H4C
retain their original path. The original physical caps, ledger, tool guard,
Seatbelt policy, Gate/Runtime/adapters and production configuration have
no changes. H4E is deliberately not enabled by this repair.

## Full verification

| Check | Result |
| --- | --- |
| Full Python main suite, Python 3.12.14 / pytest 9.1.1 | 1505 passed, 2 skipped, 7 deferred to real OS tests |
| Separate real macOS Seatbelt / owned-process tests | 7/7 passed |
| Frozen Hermes native registry test, installed Hermes Python | 1/1 passed, completing one main-suite skip |
| Distinct Python results across these runs | 1513 passed, 1 legacy fixture unavailable; no failed assertions |
| DSH Vitest 4.1.11 | 64/64 passed using `--pool=threads` |
| TypeScript 6.0.3 typecheck | PASS |
| TypeScript build | PASS, output hashes recorded |
| Code whitespace/error check | `git diff --check` PASS |
| Independent review | Prior Codex Astra Medium review: no blockers; runtime diff unchanged, no additional review run |

The remaining skipped test expects an old ledger inside this worktree.
The actual owner-global ledger was independently checked against its fixed
SHA-256 below; it was not copied into a false fixture. Python main tests
used an empty temporary Home, denied access to old private evidence, and
permitted only synthetic loopback networking. The seven kernel/process
tests ran separately to avoid nesting Seatbelt. The optional registry test
used temporary copies of existing pure-Python pytest dependencies; no venv
or global package was modified.

DSH source and lock-matched dependencies were copied to a temporary test
directory. The first fork-pool run passed assertions but logged worker
termination `EPERM`, so it was not accepted as the final result. A thread
pool rerun passed without cleanup errors under the same file/network
restrictions. The test process groups exited. No production DSH settings
or test assertions were changed.

The authentication kernel test covers original failure, repaired profile
resolution, empty profile, denied profile access and an off-proxy pool
route. Every case confirms global credential reads, profile credential
writes and networking are denied, with synthetic auth/config bytes
unchanged. Unit coverage also checks sanitized errors, wrong/empty keys,
wrong Provider, nonmanual credentials, prior-case isolation and parent
admission evidence. Existing Gate behavior is covered by the full Python
and DSH suites and has no source diff.

Public evidence: [validation log](../results/processed/phase8_3_h4d_auth_validation.log)
and [machine-readable validation](../results/processed/phase8_3_h4d_auth_compatibility.json),
including code and log SHA-256 values. The unchanged public whitelist and
privacy-validation rules are applied to the entire release; the whitelist
adds only this repair's test, reports and evidence. The final clean release
must have `publish_ready=true`; this flag grants no real-experiment authority.

## Historical state, rollback and delivery

- 32 protected historical-evidence and test-state files match the start
  of this closeout. Test-Home auth metadata matches, and auth contents were
  not read by this investigation. Its OFF config, SQLite/plugin state and
  original recovery evidence remain unchanged.
- The four original H4D owned groups are all stopped. No signal was sent
  to production processes. There is no new runtime deployment to undo.
- Historical physical ledger SHA-256 remains
  `5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`:
  **8/24**, with the original **H1 UNKNOWN** retained.
- New real Provider requests, real Agent tasks and Laya inferences: **0**.
  No H4D rerun, H4E execution, PAYG, Active/Canary, NAS/main update or merge.
- Git rollback is a revert of this repair's commit on the feature branch,
  subject to a later authorized change. The base commit, recovery Git
  bundle and reverse patch are retained with the delivery receipt. Revert
  code only; never delete or rewrite the historical experiment evidence.

The existing PR remains open, Draft and unmerged. The exact delivered
commit, source tree, public manifest digest and remote verification belong
in its final publication receipt, avoiding a self-referential commit hash
inside this committed report.

## Remaining limits and H4E

Synthetic credential compatibility does not prove the real credential is
currently valid upstream. Real H4D E2E, billing debit, model-value gains and
the original H1 missing outcome remain unresolved. No claim is made that
the original historical hidden exception is uniquely identified.

The [H4E one-shot proposal](PHASE8_3_H4E_ONESHOT_PROPOSAL.md) preserves
Step Plan `step-5-preview`, at most 3 physical requests and one 90-second
attempt, with no PAYG or automatic retries. It requires a new case and
evidence root, a separately implemented/frozen executor, renewed admission
and fresh explicit exact-source approval. Until then, **H4E execution is
NO-GO**. This window closes with the engineering repair delivered and the
next experiment unexecuted.
