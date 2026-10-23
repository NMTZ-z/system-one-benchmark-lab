# Phase 8.3A H4B: isolated, recoverable real Agent admission contract

**Prepared before any H4B StepFun Provider traffic (2026-10-23).**

H4B is a NEW case, never an overwrite or retry of the original H4
gateway-startup refusal. Original H4 on frozen source a32eb078593cb4a9139c9aa181d017b9bb010298
had zero native Agent/StepFun requests. That evidence must remain frozen.
H4B uses the OFFICIAL in-process Hermes run_oneshot/AIAgent engine,
not the CLI -z gateway-backed transport. It never starts, stops,
forces, replaces or modifies the host production Gateway.

## Explicit local protection and rollback

1. A CLEAN frozen Git source and the original cumulative eight
   StepFun physical Provider requests must be verified before any
   test Home mutation. H1 slot 1 remains attempted but without
   terminal result (UNKNOWN). H2 and H3 original results remain frozen.
   No production/NAS/GitHub main merge is permitted.

2. Only the already manually authenticated, isolated Hermes
   data Home under ~/.hermes/system-one-phase83lab is eligible.
   It must initially be OFF and credentials must point to
   127.0.0.1:18794. The independent auth.json is NEVER read by
   test helpers, copied to recovery, printed or rewritten.
   Only stat-only metadata is saved to attest that it remains
   unchanged. No production Hermes profile or credential is used.

3. A durable 0700 recovery directory is created under the
   Git-ignored original research private root BEFORE switching
   to Shadow. It contains owner-only SQLite online backup,
   one plugin state, the nonsecret test config and public plugin
   source. Every original file/digest is checked. Postrun
   native SQLite and Adapter state are archived privately
   BEFORE the original test Home's SQLite logical data, plugin
   state/source and config are restored. Test Home must end OFF.
   Restoring is idempotent; original H1/H2/H3/H4 evidence is
   never deleted or overwritten.

4. A real macOS Seatbelt policy must be in force on the native
   child process. The default rule is deny. Only exact existing
   test-Home SQLite/lock files, one private plugin-data directory,
   and a NEW h4b_missing_read case directory are writable.
   Existing test auth.json, other home files, production files,
   NAS and Git repositories are not writable. Only localhost
   ports 18793 (observer) and 18794 (physical Provider cap)
   are reachable; direct outside-Provider or Gateway egress
   is denied at the OS level. Offline macOS subprocess
   tests have verified allowed/private writes, denied writes
   outside scope (including a credential-like protected file)
   and local-port network limitations.

5. Within the same sandbox, a PROCESS-LOCAL official Hermes
   custom toolset exposes only read_file. A separate ToolRegistry
   dispatch guard denies every other tool name and any path other
   than the exact preregistered ABSENT private H4B target. The
   original Agent task asks for one native read_file and never
   authorizes shell, browse, network or writes. These changes
   exist only in the disposable native child Python process,
   never in global Hermes sources.

6. The exact same sandbox and installed official Hermes module
   MUST first pass an offline import/toolset check with zero
   native Agent/Provider requests. A failed check stops the
   experiment and restores the original Home. No weakening
   a security rule to get a passing result.

7. All local servers and the native Agent are separate process
   groups created by H4B. On any error or timeout, the harness
   terminates only its OWN process groups, never host Gateway
   or another Agent's process. Rollback requires all three
   test-only ports to be clear. The test Home source must
   remain attributable to the frozen Git commit.

## Non-refundable external Provider budget

StepFun requests are irreversible as service usage. Local
state can be rolled back, external token/credit consumption
cannot be refunded by this test harness.

Exactly one real native H4B attempt is eligible and can reserve
at most three new physical requests. The previously allocated
24-global-request cap remains binding, with 8 already used:
H1 3 attempted (2 HTTP 200, 1 UNKNOWN), H2 3 HTTP 200,
H3 2 HTTP 200, original H4 0. H4B is restricted to
slots 9–11. The old H1 unknown may not be refunded or
retroactively fabricated as successful. No alternate Provider,
pay-as-you-go key, or automatic run retry is permitted.
The physical proxy can only drain requests that have ALREADY
started, for at most an additional 80 seconds.

## Strict native H4B acceptance conditions

- One genuine Herm​es SQLite Session belonging only to H4B,
  exactly one read_file whose argument matches the private
  pre-Agent target manifest, and one same-ID structured result
  with not_found=true and real File not found: error. The
  original file never exists, no output artifact created and
  no unapproved tools, shell or write actions. Normal native
  exit required. Final text alone is not proof.
- Two genuine local Laya/MLX Completion HTTP 200 responses
  for tool_result and turn_end, exact 2/2 original SQLite
  to Adapter to HMAC HTTP identity join.
- One genuine Retry/Escalation Shadow HTTP 200 advisory,
  its own HMAC request ID and exact link to the SAME native
  tool_call and turn as Completion. Never automatically
  apply a retry, escalate a model or change native execution.
  Missing or conflicting Retry evidence is NOT VERIFIED.
- H4B's <=3 physical StepFun requests fully finalized
  without new unknowns; global ledger retains original
  H1/H2/H3 SHA-authenticated prefix and H1 unknown.
- Original test Home and public source fully reverted to
  the PRE-RUN checkpoint, auth metadata unchanged, all
  H4B-owned processes stopped, no production effect.
- Only privacy-safe aggregations may be committed; raw
  HMAC keys, native IDs, prompts, tool results, profiles,
  auth files and Provider request bodies stay Git-ignored.

A scoped H4B PASS requires ALL of the above. Any failure is
PARTIAL_OR_BLOCKED with no automatic H4B rerun. Whole Phase
8.3A remains BLOCKED historically by H1 unknown, even if
H4B passes. Active/Canary is NOT AUTHORIZED.

## Manual rollback commands from the worktree

Read-only:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_transaction.py --check

Rollback only after owned test processes have exited and the
three test ports are clear:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_transaction.py --restore

Run admission without any real StepFun request:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_real_hermes_h4b.py --check-offline --frozen-sha CLEAN_COMMIT_SHA

A real run requires separately frozen clean source and the
explicit --execute-real-step-plan switch. No recovery, source
check or inspection command ever sends a Provider request.

## Read isolation, process crash recovery and offline import evidence

Additional H4B safety checks after initial preregistration, still
**before any H4B real StepFun request**:

- macOS dynamic-loader startup requires broad initial file-read
  rights. A pure per-path allowlist caused even /bin/echo to abort,
  so it was NOT used for the Agent. The final policy combines
  required bootstrap reads with explicit OS-level DENY rules for
  unrelated owner-Home top-level files, non-test production
  Hermes profile/credential directories, other Projects and
  all earlier private H1/H2/H3/H4 run evidence. Real Seatbelt
  subprocess tests confirm an agent cannot read synthetic
  ~/.ssh, Documents, another repository, a production Gateway
  folder or original H3 evidence. This protects against local
  credential/exposure risks without breaking OS runtime loading.
  If a new unknown path or symlink cannot be safely classified,
  preflight BLOCKS rather than guessing or widening permissions.
- A stronger-than-real **zero-network rehearsal** under an
  ephemeral ignored case directory successfully imported the
  installed official Hermes run_oneshot module, registered and
  validated the single native read_file toolset, and exited with
  NO Agent request or Provider traffic. Its Seatbelt allowed
  file writes only in the disposable rehearsal folder and zero
  network. The original isolated test Home's SQLite logical
  digest, plugin state/source, config and auth stat-only metadata
  were identical before and afterward. The scratch folder
  was deleted. H4B's permanent one-shot case was NOT created.
- Reversal also detects the exact original names/digests of
  plugin state files (including the existing lock) and removes
  only new REGULAR files within that isolated plugin directory
  after the child has exited. Unexpected directories/symlinks
  fail closed. Synthetic SQLite WAL-mode tests confirm original
  session records are restored while newly produced records
  remain in the private POSTRUN archive.
- Every H4B-owned test process group is recorded with exact
  UID, PID, PGID, and kernel process start time in an owner-only
  ignored JSONL recovery ledger. The crash-recovery helper
  checks these identifiers and NEVER signals a reused or
  unmatched PID. An ambiguous state blocks termination and
  prompts manual owner inspection. Rollback will NOT modify
  SQLite while a known H4B child remains alive.
  The original production Gateway and any process group not
  explicitly recorded by this one-shot are permanently outside
  the cleanup scope.

**Crash recovery (after stopping test-only ports):**

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_owned_processes.py --status

Only when the ledger proves these are original H4B process groups:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_owned_processes.py --stop-verified

Then verify and restore the nonproduction test Home using the
existing transaction's --check and --restore operations.
The helper refuses to kill other Agent/Gateway processes,
unknown PIDs, swapped process identities or a missing provenance
ledger. The user may always inspect the private logs and decide
to stop further work if any local residue cannot be accounted for.

The real H4B one-shot is not declared successful by the
orchestrator's exit code; success must separately pass the
read-only private original SQLite/Tool, Adapter/HTTP HMAC,
Provider ledger and restoration evidence verifier.
Original H4 Gateway-block evidence remains untouched.
