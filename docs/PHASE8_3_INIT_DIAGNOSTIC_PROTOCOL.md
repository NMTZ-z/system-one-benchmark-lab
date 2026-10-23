# Phase 8.3A: credential-free native initialization diagnostic

Preregistered before native execution, 2026-10-23. This is a separate
offline diagnostic, not H4D and not a repeat of H4C. Parent project baseline:
`3057ab231b955a99529fb63c45e41e5a4746b607`. Original H4C execution remains
`8776de71a88821dffd84bfd4976927fd0cfe9c3a`.

## Fixed scope

Run the actual official `run_oneshot` / `_run_agent` / `AIAgent` initialization
in a fresh process. Never replace `_run_agent` with a successful stub.
Installed source currently identifies as Hermes v0.22.4, commit
`4d04303818b61bf3aa09278af48356315515965b`. Export only Git-tracked source;
record this commit and the actual source-file digests in each experiment.
Historical documentation naming v0.22.1 does not establish that H4C used this
same source. Do not infer the historical cause from a different reproduction.

Use fresh 0700 experiment directories with an empty disposable HOME,
HERMES_HOME, cache and temporary directory. Never import Hermes in the parent.
Reuse installed Python libraries read-only; no package install/repair, no
production profile, Gateway, NAS, credential or existing test-home writes.
No production/old test authentication content may be opened or copied.

macOS Seatbelt is mandatory before importing the native Agent. Deny all
network (including loopback), writes outside the new experiment's mutable
directory, and reads of unrelated user files. Probe a synthetic forbidden
file and raw OS socket access before each native run. A failed admission
stops the run; no unsandboxed fallback or sandbox relaxation to force PASS.
Use an allowlisted environment, a synthetic custom route and a dummy key.
An empty StepFun configuration case may exercise real credential absence,
but must never have access to an existing credential or any network.

## Observations and falsifiable checks

Record stage entry, return and exception metadata for imports/bootstrap,
config, provider choice/resolution, database acquisition, MCP startup,
actual Agent construction, client, plugins, tools, session state and turn
entry. Preserve exception type, errno, exit code and source-relative stack
locations; never record exception messages, locals, config values or keys.
Flush stage records before injection, so abrupt exits remain diagnosable.

First stop at the real conversation method boundary: this proves constructor
completion only, not a persistent native session or tool execution. A
separate request-preparation case may run actual turn setup until the SDK's
first request method, where a sentinel stops it before transport. No model
completion is fabricated. Independently count the disposable SQLite rows.

Inject SystemExit/ordinary initialization failure, process crash and timeout
at named stages. Test the currently relevant import/bootstrap boundary,
provider, MCP, constructor and tool-loading boundaries. Each case has its
own process and HOME. Repeat successful initialization in a second fresh
case to check repeatability. Any earlier genuine failure is reported as a
blocked case, not as a successful injection at an unreached stage.

Parent records child PID/PGID/UID/kernel start time. Terminate only verified
owned processes; never discover or kill services by name or port. Prohibit
child process spawning. Restore disposable HOME only after the child is
reaped and its group has no live processes. Retain before/after snapshots
and stage evidence. A separate read-only verification must compare restored
bytes and modes, confirm absence of live experiment processes and inspect
actual SQLite evidence. A failed restoration blocks further native runs.

## Acceptance and publication

Native-init PASS requires real constructor completion, correct stop boundary,
OS isolation admission, zero transport requests and independent restoration.
Fault cases require the expected reached stage/type (or explicit earlier
blocker), process exit, intact evidence and restoration. These are offline
engineering results, never real Provider E2E or Retry Shadow acceptance.

Historical Provider count remains 8/24; H1's one UNKNOWN is immutable.
The original ledger digest must remain
`5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`.
Active/Canary and new paid requests remain NOT_AUTHORIZED. H4D requires a
separate decision even after diagnostic success; unresolved historical
cause, environment fidelity or isolation gaps must be explicit in GO/NO-GO.

Regression: focused diagnostic tests, full existing Python suite, unchanged
DSH Vitest/typecheck/build, existing public release sanitizer. Publish only
source, tests, this protocol and allowlisted aggregate/report to the existing
feature branch and Draft PR #9. Never merge main or publish private evidence.
