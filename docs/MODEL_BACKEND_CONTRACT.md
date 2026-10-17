# Model Backend Contract v1 (research-only)

This contract belongs to **Model Backend Pilot v1**. It is deliberately **not** a
replacement for the production Local System One HTTP API, Adapter Contract v1,
or the Laya execution-backend protocol. No Hermes/DeepSeek Harness integration
is authorized to switch models through this interface.

## Three distinct layers

- **Platform adapter:** Hermes or DeepSeek Harness; owns Agent lifecycle,
  tool permissions, fail-open behavior and action authority.
- **Decision model provider:** Laya or TypeSafe Jev; owns model identity,
  request translation and answer validation.
- **Execution backend:** local MLX, local ANE, or remote HTTPS.

Laya on ANE is still **Laya**. Jev over HTTPS is **Jev**, not an MLX runtime.
ANE -> MLX degradation is a local Laya execution concern; it is **never**
the same as a Laya -> Jev model fallback.

## Python contract

Module: local_system_one/model_backends/contract.py

A TypedRequest contains primitive, state, instructions, criteria and request_id.
A TypedResult contains primitive, decision, probabilities, provider_id,
model_requested, model_resolved, execution_backend, request_id and latency_ms.
The optional usage and provider_confidence fields appear only when actually
available. Laya-specific token counts, ANE route reasons and action heads may
appear in an isolated extensions dictionary; they are not generic confidence.

Supported primitive subset for this pilot:

| Primitive | Semantics |
|---|---|
| choice | Distinct ordered string options. A list becomes an insertion-order-preserving map of option -> null for Jev; descriptive maps retain their descriptions. |
| score | 2–10 ordered nonempty string level descriptions, indexed from 0. Server score must match the probability-weighted index. |
| noul | Probability of true in [0,1], with false = 1-true and boolean derived at >= 0.5. |

Strict validation rejects missing or mismatched labels, unsupported request types,
nonfinite numbers, probabilities outside [0,1], non-unit total probability
(absolute tolerance 0.001), score inconsistent with weighted level
(tolerance 0.011 for decimal rounding), mismatched model IDs, and invalid token
usage. A tied Choice probability maximum is valid if the selected label is one
of the tied maxima. The validator **does not force a unique tie-breaking rule**.
The pilot bounds input content at 32 KiB and nesting depth at 32; this is a
safety limit for the pilot, not a claim about TypeSafe's API limits.

No threshold, confidence value, score level, sample label, or normalized
probability is silently manufactured to repair an invalid result.

## Existing Gate compatibility (not a new stable wire contract)

ResearchEngine is a thin facade exposing the fields already consumed by
CompletionGate and RetryEscalationGate. It wraps either model provider and
leaves both Gate implementations, candidate safety rules and production Laya
routes intact.

- LayaProvider passes the original criteria representation into the existing
  DecisionEngine; it does not rewrite MLX or ANE inference.
- JevProvider maps the original question to official HTTP JSON and validates
  the returned answers map and concrete model version.
- Gate legacy fields use backend=mlx/ane/remote_http. For remote, legacy
  token_count=-1 is an explicitly documented unavailable **sentinel**, not a
  token measurement. Measured Jev usage remains separately optional.
- The legacy Gate Choice path requires confidence. A provider lacking a
  verified confidence value fails safely rather than silently inserting 0 or 1.
- Laya's legacy confidence is kept only in extensions for legacy Gate
  compatibility. It is not reclassified as a universal model confidence.
- Both Gates remain advisory/research-only. No caller receives new Active
  authority, retry permission, paid model escalation or task-stop capability.

Completion's existing 0.70 complete threshold is preserved. If Jev is evaluated
under the **same 0.70 threshold**, that is a *shared experimental rule*, **not
a Jev-specific calibrated production threshold**. Scores and calibrated
probability claims must be evaluated separately.

## Reproducibility and remaining limitations

Every run freezes one provider and records dataset SHA-256, code commit,
strategy ID, per-case identity, requested/resolved model, backend, failures,
and client wall-clock latency. Published Jev metrics require responses from
the pinned, real API; Mock traffic cannot qualify.

No proof of general real-world superiority follows from the synthetic pilot
set. The cross-model interface is extensible but is **not** an automatic model
router, an ANE conversion, an Active Completion/Retry release, or production
switching in Hermes/DSH.
