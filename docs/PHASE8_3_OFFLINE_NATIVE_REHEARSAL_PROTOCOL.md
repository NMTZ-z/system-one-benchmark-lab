# H4D prerequisite: offline native missing-file and Shadow rehearsal

Registered 2026-10-24 before execution. Baseline `a947c4b296dfc1dd0a00f2fcd80a33c7114d00f0`.
This is a new offline experiment, not H4D or a rerun of H4C. No real
StepFun request, credential access, Active/Canary, deployment or merge.

## Scope and frozen inputs

Use the already exported official Hermes source `4d04303818b61bf3aa09278af48356315515965b`.
The current installed checkout has advanced to `bf0203a794a07aac3ff764972ab9087baa4e4f4e`;
do not mix that source into this experiment or change its installation.
Record the source archive/core-file hashes, adapter hashes, harness hashes,
interpreter and dependency metadata before each batch. Reuse existing Python
libraries read-only; no package installation. Local Laya source is pinned
to `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`; no model download permitted.

Each case has a never-used identifier, HOME/HERMES_HOME/tmp/cache and
preregistered absent file. Official plugin discovery loads copied PUBLIC
plugin source into that disposable Home. It exposes only native read_file,
with an immediate exact-name/path dispatch guard. Real Agent, tool dispatch,
file error, lifecycle hooks and SQLite persistence must execute unchanged.

Only the main Provider transport is synthetic: a standard httpx MockTransport
returns one OpenAI-protocol read_file tool-call and one final response after
independently checking the actual tool error in the second request. Maximum
two main fixture requests, no auxiliary model route, no physical Provider
network. Do not infer genuine model behavior/quality from this deterministic
fixture, or fake the tool handler, hook status, SQLite rows or adapter events.

## Four separately adjudicated cases

1. OFF: actual native read failure; no Shadow HTTP observations.
2. Shadow + fixture decision runtime: actual Local System One HTTP/Gate
   contracts with deterministic synthetic decision answers.
3. Shadow + local MLX: same native fixture and actual pinned Laya runtime.
   Preserve every hard rule. Record actual inference count; a rule-selected
   Retry response is not a model inference.
4. Shadow + service 503: owned local service deliberately returns 503;
   Agent/file/SQLite outcome must remain unchanged and adapter fail open.

Expected healthy Shadow observations: Completion after tool result and turn
end, Retry after the same failed tool. Recompute session/tool/turn/request
HMAC joins from native SQLite and lifecycle witness data; never join by time
alone. Exactly one native tool call/result, two fixture Provider requests,
and no automatic retry/model switch/extra tool. Missing or extra evidence
blocks acceptance, even if the Agent prints a plausible final answer.

## Safety and recovery

Reuse the diagnostic Seatbelt, process identity and snapshot helpers.
Native process external network is denied; the sole exception is its new
owned loopback Shadow port. Metadata/DNS, subprocess or unrelated network
attempts remain blocked. The runtime may bind only its assigned loopback
port and reads only public source/dependencies/model files. MLX may use the
Apple GPU and local Metal compiler through explicitly named OS capabilities;
no keychain, authentication, unrestricted network or production writes.
Failure of required GPU isolation admission is a reported block, never an
unsandboxed fallback. Model reads are local-only, caches go to fresh scratch.

Before native import prove forbidden synthetic read/write and unrelated
socket access denied. Record PID/PGID/UID/start time before GO; stop only
matching owned groups. Do not query or kill services by name/port. After all
owned processes stop, archive SQLite with committed WAL, snapshot postrun
state, restore disposable pre-run bytes/modes, and independently recheck.
Retain raw synthetic evidence privately; publish only bounded aggregates.

The original Provider ledger digest must remain
`5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`:
8/24 historical attempts and one H1 UNKNOWN. Original H1–H4C logs, Session
stores, snapshots, authenticated test Home and production Gateway are not
modified. H4D technical readiness and paid-run authorization are separate;
successful offline rehearsal does not itself authorize a real request.

## Validation

Test malformed/extra fixture requests, extra/forged native rows and tool
identities, missing/duplicate Shadow events, mismatched HMACs, 503 behavior,
snapshot restoration and process ownership. Run appropriate full regression
and the public sanitizer before updating the existing Draft PR #9. No merge.

## Preregistered dependency-isolation correction before the next case

The first two OFF diagnostics reached the real tool, but its missing-file
branch spawned a shell for filename suggestions and was correctly denied.
Those cases are BLOCKED, not native missing-file PASS. The final Provider
fixture now exits the child immediately on an invalid second request, so
Hermes cannot repeatedly retry a violated fixture contract.

Keep the no-subprocess sandbox. Within the disposable child only, disable
the shell environment snapshot and replace exactly the two target-parent
`ls -1` queries (Unicode filename matching and similar-file suggestions)
with actual standard-library directory enumeration. Refuse every other
command/path. Real `LocalEnvironment`, native stat/read, missing-file error
construction, tool handler, dispatcher and hooks remain upstream code.
This is dependency-isolated native evidence; it does not validate Hermes'
shell startup or shell transport. Never return a fabricated ReadResult.

The first MLX case loaded the frozen weights but its first prediction did
not finish within the unchanged adapter's five-second bound; Completion
failed open and Retry used its rule. It is BLOCKED, not MLX PASS. Before
the next native MLX case, preregister one separately counted synthetic
three-choice warmup, bounded by the runtime's 45-second admission timeout.
Do not start Hermes until warmup completes. Preserve the adapter timeout
and the current GPU sandbox while distinguishing cold start from an OS
capability failure. Warmup is not native task/value evidence.
