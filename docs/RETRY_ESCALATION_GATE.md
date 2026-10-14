# Retry / Escalation Gate (Phase 8C)

**Status:** Experimental, advisory-only, opt-in Shadow. No Active recovery.

This gate observes a **typed failure context**, not raw error logs or tool
transcripts. Its six possible recommendations are:

| Decision | Meaning |
|---|---|
| `retry_same` | Eligible to retry under the caller's verified backoff/budget policy |
| `try_alternative` | Another safe recovery approach may be worth considering |
| `escalate_model` | More reasoning ability may help, if independently approved and budgeted |
| `verify_state` | Determine whether the original side effect already happened |
| `ask_user` | Permission, clarification or verified budget information is needed |
| `abort` | Stop attempting *this recovery path*; **not** a command to stop the Agent |

## Runtime API

`POST /v1/workflows/retry-escalation-gate` with
`application/json`, example (hypothetical and safe):

```json
{
  "failure": {"category": "timeout", "transience": "unknown", "outcome_known": false},
  "operation": {
    "type": "pr_create", "side_effect": "external",
    "idempotency": "unknown", "side_effect_status": "unknown",
    "verified_idempotency_key": false, "reversibility": "unknown",
    "metadata_source": "adapter_policy"
  },
  "history": {
    "attempts": 1, "max_attempts": null, "repeated_failures": 0,
    "remaining_time_ms": null, "retry_budget_available": false
  },
  "constraints": {
    "requires_approval": false, "escalation_allowed": false,
    "escalation_budget_available": false, "alternative_available": false
  },
  "request_id": "example-request"
}
```

The deterministic result recommends `verify_state`. Output includes
`guarded_decision`, `raw_model_decision` (null for rules),
`decision_source`, `safety_override_reason`, `backend`,
`route_reason`, `latency_ms`, `request_id` and `advisory_only: true`.
Model choice is allowed **only** after all hard rules have filtered candidate
decisions. No execution or network writes are performed by the Gate.

### Permission and retry-budget invariants

- An unknown write, Git Push, PR create, or external side effect must be
  verified first. Known mutating operation types (`write`, `git_push`,
  `pr_create`) cannot declare `side_effect: none`, even if accompanied
  by `metadata_source: adapter_policy` or a claimed idempotency guarantee.
  Both `write` and `external` remain conservative mutating effect classes;
  the existing frozen benchmark is not rewritten to enforce locality distinctions.
  An `unknown` side effect is never direct-retry eligible. A verified idempotency key does not by itself establish
  that an unconfirmed write never happened.
- HTTP 401/403 cannot become an automatic retry loop. 429 requires a trusted
  Retry-After *and* remaining caller-controlled budgets before even recommending
  `retry_same`. The gate never sleeps, retries, switches models or approves tools.
- Null retry budget or missing attempt ceiling means **unknown**, not unlimited.
- Unknown tool identity or failed-event evidence is `unsupported` at the adapter;
  ambiguous provider errors are not fabricated into tool failures.
- No instructions, free-form error strings, trace, credentials, or tool arguments
  are accepted by the new Runtime request schema.

## Adapter opt-in

Hermes plugin v0.9.0: `retry_escalation_gate_enabled: true` together with
`mode: shadow`. DSH adapter v0.6.0: `retry_escalation_gate_enabled: true`
and `mode: shadow`. **Default false** independently in both.

No production configuration is changed by this source release. Both adapters
use existing normal runtime service URL and timeout; they never grant recovery
action authority even under `mode: canary`. The watcher is bounded (2 failure
events per turn, 4 in-flight requests) and returns without waiting for inference.
Turn/session lifecycle state is cleared. Response failures fail open.

Pinned operation policy is intentionally narrow: Hermes recognizes read_file /
web_search / web_extract as reads and write_file / file_edit as writes; DSH
recognizes read/web_fetch/web_search/Tavily as reads and write/edit as writes.
Unknown shell, arbitrary MCP or provider exceptions are **unsupported** rather
than guessed. This limits coverage and will require separately audited native
tool policies if expanded.

## Adapter Contract v1 compatibility

Gate enum `retry_escalation` is an **opt-in additive extension** of the
existing Decision Envelope/Telemetry schema. The version string stays `1.0`,
but older strict clients may reject this new gate label. Existing gates retain
their wire formats. New envelopes must **never** be sent unsolicited to old
adapters; both plugin flags are disabled by default and old agents never
receive Retry decisions. A cross-platform auto-executing controller would
require its own independently versioned contract/authorization design.

## Limits

The initial Shadow observer covers trustworthy structured **failed tool
results** only. Genuine provider exceptions, generic shell output with
ambiguous success, incomplete lifecycle identities, approval state, verified
per-call retry budgets, and the full alternative-tool inventory remain
unavailable in the audited hooks. These are not a reason to parse private
exception messages or to infer side-effect safety.
