# Phase 8.3A H4C: distinct, reversible Hermes native tool-failure evaluation

**Registered 2026-10-23, BEFORE any new H4C StepFun request.**
**This is not a rerun of H4 or H4B; their original evidence remains immutable.**

## 1. Goal and previous evidence

H4 on frozen source a32eb078593cb4a9139c9aa181d017b9bb010298
failed at production-owned Gateway admission. H4B on frozen source
633c914fe9b78b7515cfcfbe4795f5d2dbd3aadf was stopped by
macOS Seatbelt denying harmless /dev/null output before native
AIAgent construction. Both had ZERO StepFun physical requests
and each has independent archived incident and rollback evidence.

The new case H4C uses the official in-process Hermes run_oneshot/AIAgent
(not the Gateway-backed CLI). Its purpose is to obtain ONE real native
read_file failure on a guaranteed absent disposable file, plus actual
Completion and Retry/Escalation Shadow observations linked to the
same original SQLite tool-call ID. An Agent's own final text alone
is never accepted as proof of a failed native tool or Retry advice.

## 2. Physical StepFun Plan budget, unchanged

Original cumulative private Provider ledger SHA-256:

    5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb

The original eight attempts are: H1 3 physical (2 HTTP 200
and one UNKNOWN), H2 3 HTTP 200, H3 2 HTTP 200, original H4
and H4B both 0. H4C may reserve ONLY slots 9 through 11, maximum
three; the 24-global hard cap, original 8 reservations and
H1 missing terminal record must never be reset or rewritten.

Only existing operator-authorized StepFun Plan step-5-preview via the
bound localhost 127.0.0.1:18794 physical pre-network limiter is
permitted, never pay-as-you-go or alternate Provider. The proxy
can drain already-started network requests for at most 80 s
after native exit, but must not initiate another Agent turn.
A StepFun request is externally nonrefundable, so no more
requests are authorized by the mere existence of unused slots.

## 3. Local reversible isolation

Existing independently authenticated test-only Hermes Home:

    ~/.hermes/system-one-phase83lab

The test Home MUST start OFF, with the manual test credential
route pinned to loopback 18794. No production Hermes Home,
auth file, NAS/Git repository or Gateway may be accessed or
modified by the test. No provider API token contents may be
read, printed, moved or copied by the test/recovery helpers.

H4C uses NEW private nonproduction folders:

    private/phase8_3_native_real/runs/h4c_missing_read/
    private/phase8_3_native_real/h4c_recovery/

These are distinct from original H4B, whose own run and
recovery directories are preserved unchanged. Admission
requires independent revalidation of the original H4B
frozen incident, its 4/4 stopped test-only process groups,
original test Home restoration and original ledger SHA.

The transaction takes a 0700/0600 durable ONLINE SQLite backup,
original plugin JSON, lock, public plugin source and OFF test
config BEFORE any Shadow switch. It preserves post-run SQLite/
plugin evidence separately and restores the exact pre-run
test Home logical database, plugin state/source, config and OFF
mode. Only stat-only credential metadata is compared, never
credential file contents.

All native, observer, model and capped Proxy processes are new,
case-owned process groups. Cleanup records PID, PGID, UID and
kernel start time. A missing/changed ownership record prevents
unsafe process termination or live SQLite restore. Rollback can
be run independently by the owner after only verified H4C-owned
processes have stopped; there is NO kill-by-name or global
Gateway restart.

The native child runs inside macOS Seatbelt (default DENY),
with allowed writes restricted to the new H4C disposable
folder, existing test SQLite/locks, one test plugin state
folder and the harmless nonpersistent /dev/null output sink.
External networks are denied except localhost 18793
(HMAC Observer) and 18794 (Provider cap). Known owner-private
directories, unrelated Hermes profiles, previous runs and
repositories are denied for reads/writes. No arbitrary
terminal/shell/browser/network tools are exposed.

A per-process official custom Toolset permits ONLY read_file.
The native dispatcher additionally checks its requested path
equals the original newly generated, ABSENT H4C target
recorded in a private 0600 manifest BEFORE the Agent starts.
The prompt forbids writes, other tools, invented content,
path substitution and retry.

Ancillary local MLX/Observer/Provider services additionally
use an H4C-owned disposable HOME/TMPDIR/cache, not the owner's
usual HOME. The native child retains original user HOME only
to locate the FIXED isolated HERMES_HOME.

## 4. Mandatory zero-cost admission

Before H4C real StepFun:

1. Source committed to a CLEAN exact frozen SHA and pushed
   to Draft PR #9. Python full suite, DSH Vitest/typecheck/
   build and public release sanitizer must PASS.
2. H4C original run and recovery folders do not yet exist.
   Original H4/H4B private files and all eight physical
   Provider events have their original hashes.
3. Test Home OFF/READY and correct proxy route; no test
   port 18782,18793,18794 has an existing listener.
4. Mac Seatbelt real subprocess must prove write, read and
   local network restrictions. A disposable H4C rehearsal
   imports the installed official Hermes run_oneshot and
   executes its stdout/stderr preamble with a synthetic
   no-model stub. ALL network is forbidden and test Home
   digests before/after must be identical.
5. After the durable pre-run recovery checkpoint and Shadow
   switch, the same real Seatbelt profile must pass its
   --check-offline native child test BEFORE the real
   MLX/Observer/StepFun proxy starts.
6. If any check fails, terminate ONLY new H4C-owned child
   groups, restore the test Home, record blocker and STOP.
   NEVER relax Seatbelt, retry automatically or falsify
   native/Provider evidence to obtain a favorable result.

## 5. Independent actual acceptance

NATIVE: Exactly one original Hermes SQLite Session belonging to
H4C, one read_file call whose arguments match the pre-Agent
manifest, paired same-ID tool result with not_found=true,
real File not found: error, no successful file content,
no other tools, no file mutation and normal native exit.

COMPLETION: Two genuine local Laya/MLX HTTP 200 observations
for native tool_result and turn_end, exact 2/2 keyed native
SQLite to Adapter to Observer identity links.

RETRY: One real, advisory-only Retry/Escalation HTTP
observation linked to the same original native failed tool
and turn. The model's guarded decision must not cause
an automatic native retry, change tool or escalate execution.

PROVIDER: 1-3 genuine physical StepFun attempts only in
H4C slots 9-11, all terminal and recorded without a new
unknown. H1's original unknown remains unchanged.

ROLLBACK: Original test Home OFF and pre-run SQLite/plugin/
config/source fully restored, credential stat unchanged,
all H4C-owned process groups stopped and postrun private
evidence retained. No persistent production changes.

A scoped PASS needs EVERY condition, otherwise report
PARTIAL_OR_BLOCKED and do not automatically rerun H4C.
Phase8.3A overall retains historical H1 Provider integrity
BLOCKED. Active/Canary remains NOT AUTHORIZED, actual plan
cost and Agent-level savings are NOT measured.

## 6. Emergency manual recovery (H4C ONLY)

Read-only process verification:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_owned_processes.py --case h4c_missing_read --status

Only exact H4C recorded PID/PGID/UID/start-time groups may stop:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_owned_processes.py --case h4c_missing_read --stop-verified

Only when the test ports are free, inspect and restore:

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_transaction.py --case h4c_missing_read --check

    ../system-one-benchmark-lab/.venv/bin/python scripts/phase8_3_h4b_transaction.py --case h4c_missing_read --restore

These commands never target original H4B backups. Raw logs and
snapshot data remain Git-ignored and owned by the operator.
