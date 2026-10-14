# Phase 8C Failure Audit (pre-implementation)

Date: 2026-10-14. Scope: a new opt-in, **Shadow-only** Retry / Escalation Gate.
This is an audit of *observable information*, not a claim that either platform's tool
event proves non-execution. It does not establish production E2E readiness.

## Repository baseline and version isolation

- GitHub public main: `ca9d671986dcfc1f4a06931069694d161f6370ac` (PR #4 merged).
- NAS `origin/main`: `afa2512cc66400d111c28cb5fe00e9f83fdba49a` (older than public 8B);
  NAS private 8B branch: `527f031da038d55573ea1f7104b37e042b397b50`.
- New isolated 8C worktree branches from **GitHub public main**; development changes
  will be mirrored to an independent NAS feature branch. This does not rewrite or
  synchronize the older NAS main or touch Phase 8B's existing worktree.
- Existing adapter releases: Hermes plugin 0.8.0; DSH adapter 0.5.0.
- Installed Hermes: `v0.21.7+495.g6e7b83a`, local commit `6e7b83a2f1c0`.
- Frozen inspected DSH upstream: `0.1.7-rc.2`, commit
  `477b4f420553e8a52c2fbccc464d7561b239c443`.
  Adapter peer range names `0.1.7-rc.2 || 0.2.1-alpha.1`; **the latter is not verified here**.

## Failure and hook mapping

| Item | Hermes installed source | Frozen DSH upstream |
|---|---|---|
| Failure observation | Native `post_tool_call`, `agent/inline_tool_executors.py` dispatch | `session/event` `tool/result`, `packages/core/agent-loop/src/tool-calls.ts` |
| Identity | `turn_id`, `task_id`, `session_id`, `tool_call_id`; `function_name` | `session.id`, `data.turn`; join `tool/call.data.callId` to `tool/result.data.message.source.callId` |
| Explicit failure indicator | `status`, `error_type`; optional structured result | `message.isError === true`, `data.error.{name,code}` |
| Outcome uncertainty | timeout, cancel, ambiguous tool result can have continued side effects | `isError` does **not** prove the operation never took effect |
| Turn cleanup | `on_session_end` for observed identity (also LRU cap) | `turn/end`, `session/end` / `session/close` |
| Limits | post_tool result is raw and may contain secrets; **do not forward or log** | tool `arguments`, tool result content and `error.reason` may contain secrets; **do not forward or log** |
| Provider failures | not reliably attributable to a distinct tool operation through this hook | not reliably present as `tool/result`; `turn/end` reason alone insufficient |
| Retry authority | Hermes has independent API retry settings, tool deadlines and approval handling; no trustworthy per-call retry budget passed to this hook | DSH native tool/provider retry and rejection control remains upstream; no trustworthy recovery budget exposed in these events |

### Supported observation

Only explicitly failed **tool** events are eligible. Use structured signal, not
substring matching on error messages; successful tools must not trigger.
Unknown operation identity, unsupported lifecycle identity, unverified outcome or
absent tool/call pairing must not be guessed into a safe retry. A known write
or external side effect with unknown execution outcome yields the independent
semantic advice `verify_state`, never `retry_same`. Where identity or failure
evidence cannot be established, report `unsupported` in adapter telemetry
without calling Runtime. The first iteration cannot reliably classify arbitrary
provider failures, unknown tools, intermittent DNS vs network failure from raw
free-form strings, or internal framework exceptions not emitted at the hook.

## Failure taxonomy and trust boundary

Allowed categories: `timeout`, `network`, `rate_limit`,
`server_error`, `auth`, `validation`, `tool_error`,
`test_failure`, `logic_failure`, `partial_success`, `unknown`.
Only protocol fields / adapter-pinned tool policies may set idempotency,
side-effect status, execution-known state. No Laya classification from text.
A reported 429 requires a trusted Retry-After value, external budget and
caller-managed delay. HTTP 401/403 cannot be overcome by retry.
Generic shell/exec/delegation tools are marked unsupported without a verified
operation classifier.

## Design choice / explicit limits

- Gate decisions are six **advisory labels**, with no tool execution, stop,
  permission change, paid model switch or retries.
- Fixed schema in v1 is extended **additively** with the new gate enum; old
  clients that reject unknown gate values must never receive it unsolicited.
  Both new adapters require their own default-OFF config.
- Separate retry observer from Completion's hooks/state and never infer retry
  from Completion `continue`.
- Bound concurrency, observation count, request fields and telemetry. Do not
  record full raw traces or error messages. Record `unsupported` instead of
  manufacturing context.
- No verified end-to-end Agent recovery was observed at this audit point.
