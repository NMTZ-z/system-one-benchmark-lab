# Phase 8.3A — optional native Hermes stock-shell qualification

## Preregistration and scope

This is a **new, opt-in, OFF-only** experiment on the frozen upstream Hermes
source `4d04303818b61bf3aa09278af48356315515965b`. It is distinct from,
and does not rewrite, the four-case offline native/Shadow rehearsal, H4,
H4B/H4C or the blocked real H4D. Its aim is to close the **native shell
transport dependency gap** identified in the four-case rehearsal. It is not
an Active/Canary experiment and cannot establish real StepFun task quality,
Retry decisions or Agent-level savings.

The implementation is an additional CLI case, `off_stock_shell`, in
`scripts/phase8_3_native_rehearsal.py`. The existing default case set remains
`off`, `shadow_fixture`, `shadow_mlx`, `shadow_503` and retains its original
no-subprocess policy and narrow Python directory-enumeration bridge.

Unlike those four cases, **this one does not monkeypatch** upstream
`LocalEnvironment.init_session` or `ShellFileOperations._exec`. Upstream
Hermes genuinely creates its login Bash snapshot and uses the real shell
transport for missing-file lookup. The Hermes AIAgent, native `read_file`,
dispatcher, lifecycle hooks and SQLite persistence are also unmodified.
The **main Provider alone** uses the existing strictly capped in-memory
OpenAI-protocol two-response fixture, which must receive and verify the
actual native tool error before producing a final response. There is no
external Provider connection or real main-model decision.

## Isolation and fixed admission requirements

- Use an official **credential-free Git archive**, not the live production
  checkout; six upstream key-file SHA-256 values are fixed in
  `STOCK_SOURCE_SHA256` and enforced before launching.
- Use one new Git-ignored case root, a disposable HOME/HERMES_HOME/tmp/cache,
  and the existing process PID/PGID/UID/start-time ownership registration,
  cleanup, native SQLite backup and rollback verification.
- Use macOS Seatbelt: deny-by-default external network and sensitive/user
  file reads; write access only within this one disposable mutable tree.
  Test **actual** forbidden read/write and network denial before admission.
- The stock case alone adds `process-fork` to its disposable child policy.
  Its Python audit hook permits only `/bin/bash` plus upstream's fixed
  environment probes (`python3`, `uname`, `file`) from disposable cwd,
  refusing other Popen calls. The shell's OS descendants inherit the
  file/network sandbox. The old four cases do **not** acquire this grant.
- Agent tool dispatch must be exactly one `read_file` of the preregistered
  missing scratch path. No other tool, write, retry or escalation is allowed.
- No production Gateway, production Hermes/DSH Home, NAS `main`, StepFun
  authentication, Provider proxy or payment ledger may be altered. Do not
  infer any new paid-test authorization from this work.

## Predeclared independent PASS conditions

1. Native SQLite: one Session, one native `read_file` call, matching tool
   result ID, structured `not_found=true` and `File not found:` error, and
   one final assistant response after the real error.
2. Exactly two synthetic main Provider responses; zero physical Provider
   requests, no unexpected Agent/tool action and no Shadow HTTP request.
3. At least three actual upstream Bash spawns, including one login Bash
   snapshot and at least two subsequent Bash invocations. No
   `dependency_isolated`/`directory_listing` bridge event or denied unknown
   shell process. Fixed upstream non-Bash probes are separately counted.
4. Kernel-level forbidden-file read/write/network checks pass. All owned
   processes terminate, disposable Home and runtime scratch are restored,
   original absent target remains absent and protected sentinel is intact.
5. Result verifier rejects absent/altered native SQLite, missing native
   events, forged shell witnesses, incomplete rollback or unexpected side
   effects. Keep private child logs and process receipts out of Git.

## Reproduction and evidence hierarchy

After preparing a fresh fixed-source archive and interpreter, run:

```sh
python scripts/phase8_3_native_rehearsal.py \
  --source /path/to/credential-free-hermes-4d043-archive \
  --python /path/to/isolated-hermes-python \
  --case off_stock_shell \
  --output /path/to/new-private-run
python scripts/phase8_3_native_rehearsal.py \
  --verify /path/to/new-private-run/off_stock_shell
```

The output directory must not already exist. All actual child code, native
source-file hashes and outcome receipts must be recorded before claiming
this bounded result. The public report must contain only aggregate counts,
versions, source digests and acceptance limits, never raw Session IDs,
file paths, credentials or raw tool messages.

**Evidence labels:** OFF native tool + stock shell + *synthetic* main Provider
is an offline dependency-compatibility proof. It is **not** a real-Provider
H4D, a new native Agent value benchmark, a Shadow Retry model result or
subscription cost evidence. Global Phase 8.3A real-Provider qualification
remains blocked by the original H1 UNKNOWN and unfinished H4/DSH cases.
