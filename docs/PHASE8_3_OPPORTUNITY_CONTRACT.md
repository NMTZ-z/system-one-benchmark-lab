# Phase 8.3 — Decision Opportunity Contract v1

**Status:** isolated offline/Shadow analyzer implemented. Not Adapter Contract v2, not a Gate, not a router, and not an execution permission. Phase 8.3 does not activate Completion or Retry.

## Goal and integration boundary

A decision opportunity is a **classification of an observed, normalized decision point**. It answers whether the point is already decided by trusted deterministic policy, has bounded safe choices for a local Typed Decision model, needs the native Agent to plan/generate, or lacks sufficient trustworthy evidence.

The implementation is `local_system_one/decision_opportunity.py`, a pure validator/classifier with no network, model import, Agent hooks, state database or token budget access. Inputs are metadata only. Producers must keep text, prompts, platform IDs, raw errors, file contents, headers, secrets and tool arguments **out of the contract**. Strict allowlists and bounded registered labels reject unknown free-text fields.

The implementation **reuses the Phase 8.2B `validate_capabilities()` declarations** for platform evidence. It is orthogonal to Model Backend Contract v1: `model identity` describes which weights generated an answer, `execution backend` describes where computation actually ran, and neither conveys authority. Existing Adapter Contract v1 and all production Gate thresholds remain unchanged.

## Contract fields

Schema: `local-system-one/opportunity-v1`.

| Field | Meaning |
|---|---|
| `gate` / `observation_stage` | Bounded Gate name and `pre_tool / post_tool / turn_end / on_error` |
| `evidence.source/status` | Existing 8.2B source/status enums; independently checked source provenance is **not** the same as an independent real-world task outcome |
| `evidence.capabilities` | Existing 8.2B capability declarations; `required_capabilities` names which are necessary for this point |
| `evidence.verified_conditions` | Declared aliases whose conditional platform capability has actually been established **by the external independent collector**; a string alone cannot authenticate it |
| `rule.resolved/decision/source` | A trusted deterministic policy outcome, not a model's interpretation of whether rules apply |
| `candidates.labels/bounded/stable/guard_source` | Stable finite candidate labels, and trusted adapter-policy preprocessing; at most 12 labels |
| `constraints` | Whether planning/generation is required, whether permissions are verified, actual side-effect state, retry/escalation *policy eligibility* and the need for independent verification |
| `authority` | Always `{"mode":"shadow","action_allowed":false}`; other modes are rejected |

Candidates are registered, bounded decision labels, not arbitrary natural-language responses. For the first benchmark, only Completion and Retry are evaluated deeply. Search, Model Tier and Notification are regression/sample-only; no new Gate implementation is introduced.

### Precedence (fail closed for classification, fail open for existing Agent execution)

1. Missing, ambiguous, unsupported or untrusted evidence, or absent required capability ⇒ **`unsupported`**.
2. Trusted deterministic policy has already fixed the answer ⇒ **`rule_only`**.
3. The decision requires new content, planning or exploration ⇒ **`native_agent`**.
4. Candidate set absent, unbounded, unstable or not safety-prefiltered ⇒ **`unsupported`**.
5. A prechecked finite set contains two or more eligible labels ⇒ **`typed_model_candidate`**, with **no execution authority**.

An eligible model candidate `retry_same` still requires a trusted adapter to mark `retry_policy_eligible=true`; `escalate_model` similarly requires `escalation_policy_eligible=true`. The same eligibility checks apply even if a deterministic rule directly recommends a recovery action. These are **untrusted claims until independently checked against original adapter policy**. The offline schema refuses inconsistent inputs but **cannot itself establish a permission, financial budget, side-effect classification or idempotency guarantee**.

Low-confidence abstention stays possible by keeping conservative `verify`, `ask_user` or equivalent safe options. A model cannot create its own candidate set, declare an operation safe, change an Agent's stop criterion, or grant permission to retry/escalate. For Shadow, `permission_verified=false` may still allow **advisory classification** if the trusted safe candidate set is valid. It **never** authorizes executing a suggested operation.

## Native evidence versus synthetic replay

A Phase 8.3 Native Agent case must retain private and independently verified causal linkage:

native tool/turn → adapter → decision request → local Runtime → Shadow recommendation, plus independently checked task outcome.

Phase 8.2B Evidence Contract, conditional capability coverage, HMAC opaque refs, request correlation and budget ledger remain the source of truth. The Opportunity analyzer does not duplicate or replace that verification.

The optional `benchmarks/decision_value/capture.py` reads **already-public Phase 8A/8C editorial cases**, checks them with existing deterministic policies and records structurally checked inputs as `independently_verified` for the **synthetic policy-replay scope only**. Its group `source=synthetic` or `public_reconstruction` is mandatory, Native baseline is null, and no native platform capability is claimed. This must **never** be quoted as independently verified *real Agent task success* or as new blind data.

## What stays out of scope

No new dynamic scheduler, delegation engine, switchable Provider, background daemon, Dashboard, global database or Active/Canary wiring. No JevAny source, data, prompt, model, package or implementation has been incorporated. JevAny's bounded-choice methodology is inspiration only, not a software dependency.

The analyzer is useful if it identifies places where **the optimal model action is not to call a model**. That is a valid result, not a defect to tune away.
