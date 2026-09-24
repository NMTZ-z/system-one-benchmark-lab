# Model Tier Gate v0.1

Date: 2026-09-24
Status: functional MVP

## Goal

Choose whether an agent task should use a fast/cheap generative model or a stronger/slower model.

The gate is not trying to rank models globally. It decides whether the current task justifies spending more reasoning capability.

## Endpoint

POST /v1/workflows/model-tier-gate

Request fields:

- task
- optional context
- risk: auto / low / medium / high / critical
- task_type: auto / transform / simple_qa / reasoning / coding / research / planning
- irreversible
- requires_precision
- request_id

Response fields include:

- tier: fast / strong
- decision_source: rule / model
- reason
- difficulty_score
- probability_strong
- backend and route metadata

## Policy

### Hard strong

Strong is selected without model inference when:

- risk is high or critical;
- the action is irreversible;
- the caller explicitly requires high precision.

These are safety/cost-of-error policies, not model intelligence judgments.

### Hard fast

Fast is selected for bounded low-risk transformations when the input context is already supplied.

Examples:

- rewrite a supplied paragraph;
- proofread supplied text;
- translate supplied text.

### Model fallback

Everything else becomes a Score decision from 0 to 4:

0. routine/direct;
1. light reasoning;
2. moderate reasoning;
3. complex reasoning;
4. expert-level deep reasoning.

Initial strong threshold: expected score >= 2.0.

This threshold is a product baseline and must later be tuned from real workflow outcomes.

## Real 421M smoke

Observed on the real local checkpoint:

| Task | Result | Source | Difficulty |
|---|---|---|---:|
| supplied low-risk rewrite | fast | rule | 0.0 |
| explain Python list vs tuple | fast | model | 1.3404 |
| design a fault-tolerant 24/7 multi-agent architecture | strong | model | 2.3408 |
| modify production authentication policy | strong | rule | 4.0 |

The complex architecture task produced P(strong levels 3+4) = 0.4768, while the simple Python explanation produced 0.1565.

This is a functional sanity check, not a benchmark.

## Product role

Model Tier Gate is intended to sit before expensive generative inference:

~~~text
agent task
    |
    v
Model Tier Gate
   /       \
 fast     strong
 model     model
~~~

The actual model names remain configuration owned by the calling agent system. Local System One only returns the tier.

## Why not let the generative model self-select?

Because asking the expensive model whether it was necessary already pays the expensive-model cost.

A small local decision model can make that choice first.

## Known limitations

- The current 421M checkpoint was not trained specifically for model-tier routing.
- The 2.0 threshold is not yet calibrated on real user outcomes.
- Strong does not mean a particular vendor/model.
- Human-confirmation policy remains a separate workflow.
- Some tasks may be cheap computationally but high consequence; hard risk rules intentionally override model difficulty.

## Next validation

Integrate into real agent traffic and record:

- selected tier;
- whether the user/agent later escalated;
- whether fast-tier output required redo;
- strong-model calls avoided;
- estimated latency/cost avoided.

The future blind set should be built from those real outcomes rather than synthetic prompts.
