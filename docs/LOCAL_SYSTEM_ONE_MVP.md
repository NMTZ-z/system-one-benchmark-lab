# Local System One MVP — Product and Technical Specification

Status: Phase 5 implementation started
Date: 2026-09-24

## Current implementation status

Implemented in the private research repository:

- normalized Choice / Score / Noul request schemas;
- MLX runtime adapter;
- fixed L512 ANE runtime adapter;
- token-length router with configurable thresholds;
- ANE startup/runtime health state;
- transparent ANE failure fallback to MLX;
- privacy-safe in-memory metrics;
- loopback-first standard-library HTTP service;
- optional bearer authentication for non-loopback binding;
- CLI entry point;
- unit tests using fake runtimes.

Verified smoke path:

- MLX-only service starts successfully;
- GET /health succeeds;
- POST /v1/choice succeeds on a real 421M checkpoint;
- a 93-token invoice-routing request is correctly routed as short_input to MLX;
- GET /metrics records backend, route and latency without raw prompt/state content.

Real service-mode L512 ANE smoke:

- the validated L512 package loaded successfully through the service runtime;
- startup probe completed without a selected-decision mismatch;
- startup rolling P50 was 166.5 ms against the initial 125 ms health envelope;
- HealthGate therefore marked ANE degraded instead of exposing the slow runtime as healthy;
- a 444-token request was automatically routed through MLX with route reason ane_unhealthy;
- the request completed successfully and the caller did not need to handle accelerator state;
- Core ML action-head overflow warnings were observed during the probe, but no non-finite final response or runtime error propagated.

This is the intended safety behavior and confirms that the runtime-state sensitivity discovered in Phase 4 is now handled by the product layer.

Not yet completed:

- production health-envelope tuning and re-probe policy;
- MCP / AgentDock / Hermes integration;
- persistent launchd deployment;
- public repository extraction.

Search Gate v0.1 is now the first functional product workflow. Design notes and the real model-only failure that led to the volatile-fact hard gate are recorded in `docs/SEARCH_GATE.md`.

## Product goal

Build a local Apple Silicon service that gives agents a dedicated System One decision layer.

It handles questions such as:

- Which agent should handle this task?
- Does this request require current web information?
- Is a stronger model worth the cost?
- Does an action require human confirmation?
- Is a notification important enough to interrupt the user?
- Should a failed tool call be retried?
- How strongly should a candidate be scored?

It does not generate prose. Generative models remain responsible for planning, explanation and content creation.

## Product hypothesis

Many high-frequency agent decisions do not require a large generative model. A small typed probabilistic model can make them locally, cheaply and quickly.

The first user is our own Mac mini agent ecosystem. The public project can later make the same capability easy for other Apple Silicon users to deploy.

## Decision primitives

### Choice

Select one labelled option and return a probability distribution.

Uses: execution-agent selection, model tier, recovery strategy.

### Score

Return a probability distribution over an ordered scale plus expected score.

Uses: difficulty, urgency, content quality, execution risk.

### Noul

Binary proposition decision with probability.

Uses: should search, should notify, should retry, requires human confirmation.

## HTTP API

Initial endpoints:

- POST /v1/choice
- POST /v1/score
- POST /v1/noul
- GET /health
- GET /metrics

Normalized request:

- state;
- instructions;
- primitive-specific criteria/options;
- optional non-sensitive request metadata;
- optional routing override for diagnostics.

Normalized response:

- primitive;
- selected decision or score;
- probabilities;
- confidence;
- action probability when available;
- backend;
- token count;
- latency;
- health/routing metadata.

Callers must not need to understand Core ML fixed shapes.

## Runtime architecture

~~~text
Agent / Hermes / AgentDock / MCP
              |
              v
      Local System One API
              |
              v
        Decision Router
        /      |       \
      MLX   L512 ANE   MLX
     short   suitable  fallback/long
              |
              v
          Health Gate
~~~

### MLX responsibilities

- short-input path;
- over-capacity fallback;
- ANE-unhealthy fallback;
- correctness reference.

### L512 ANE responsibilities

- energy-efficient medium/long decisions;
- fixed-shape accelerated path.

### Router

Initial configurable policy:

~~~yaml
router:
  ane_min_tokens: 192
  ane_max_tokens: 512
~~~

The 192 threshold is only a Phase 4 baseline. Future routing may consider token count, backend health, recent latency, queue depth, power policy, confidence and workload type.

## ANE health gate

Phase 4 observed meaningful latency-state variation from the same L512 package.

Startup probe:

1. load ANE;
2. run a small fixed probe set;
3. verify finite outputs;
4. verify expected decisions;
5. verify latency against a configurable health envelope;
6. mark ANE healthy or degraded.

Runtime behavior:

- maintain rolling latency samples;
- detect sustained latency-regime degradation;
- disable ANE temporarily when unhealthy;
- route transparently to MLX;
- periodically re-probe;
- never force the caller to understand accelerator state.

Correctness takes priority over automatic recovery.

## Integration order

1. generic HTTP client;
2. MCP server;
3. AgentDock;
4. Hermes.

The service remains independent of any one agent framework.

## First real workflows

### Search Gate

Question: Does this task require external/current information?

Primitive: Noul.

Goal: avoid unnecessary search while reducing stale offline answers.

### Model Tier Gate

Question: Is this task difficult enough to justify a stronger/slower model?

Primitive: Choice or Score.

Goal: reduce expensive model calls and reserve strong models for high-value tasks.

### Notification Gate

Question: Is this event important enough to interrupt the user now?

Primitive: Noul or Score.

Goal: reduce noisy agent notifications.

Agent assignment and retry/human-confirmation gates follow after these are stable.

## Observability

Record by default:

- timestamp;
- primitive;
- backend;
- token count;
- latency;
- selected result;
- confidence;
- health state;
- route reason;
- caller-provided non-sensitive request id.

Do not persist raw state/instructions by default. Debug payload capture must be explicit and have a retention policy.

## Privacy and security

- local-only by default;
- bind loopback by default;
- no third-party telemetry;
- no raw request logging by default;
- no secrets in benchmark/output JSON;
- require explicit auth before any non-loopback binding;
- integrations pass the minimum state needed for a decision.

## Product success metrics

Decision quality:

- human agreement;
- downstream correction rate;
- false-notification rate;
- missed-required-search rate;
- inappropriate model-tier routing rate.

Efficiency:

- decision latency;
- large-model calls avoided;
- web searches avoided;
- estimated API/model spend avoided;
- local energy where measurable.

Reliability:

- service uptime;
- ANE health-gate fallbacks;
- route stability;
- crash/error rate.

## Agent Decision Blind Set

Do not invent the final benchmark now.

After real deployment:

1. collect representative decisions from actual workflows;
2. redact sensitive information;
3. label outcomes;
4. freeze a held-out blind set;
5. only then fine-tune or optimize models.

Compare the frozen set across Jev zero-shot, base/local Laya, any future locally tuned model, and a small generative-LLM baseline where useful.

A broad best-local-agent-decision-layer claim is allowed only after that evaluation supports it.

## MVP v0.1 acceptance criteria

MVP is complete when:

- Choice, Score and Noul HTTP endpoints work;
- MLX backend works;
- L512 ANE backend works;
- automatic routing works;
- ANE health gate can force transparent MLX fallback;
- the three initial real workflows are integrated;
- requests are private by default;
- backend/route/latency metrics are recorded;
- the service survives restart;
- a minimal MCP integration works.

The acceptance target is real workflow improvement, not one synthetic latency number.

## Public open-source target

The current benchmark repository remains the private research lab.

After MVP stabilizes, publish a separate repository with working name **local-system-one**:

~~~text
local-system-one/
├── local_system_one/
│   ├── api/
│   ├── runtime/
│   │   ├── mlx/
│   │   ├── ane/
│   │   └── router/
│   ├── health/
│   └── metrics/
├── integrations/
│   ├── mcp/
│   ├── agentdock/
│   └── hermes/
├── examples/
│   ├── search_gate/
│   ├── model_tier_gate/
│   └── notification_gate/
├── docs/
├── tests/
└── README.md
~~~

The public release must clearly attribute upstream Laya/ANE work and distinguish it from this project's extensions.

## Phase 5 implementation order

1. freeze Phase 4;
2. implement service schemas and normalized responses;
3. implement MLX runtime adapter;
4. implement L512 ANE runtime adapter;
5. implement token-length router;
6. implement startup/runtime health gate;
7. implement HTTP service;
8. add metrics and privacy-safe logs;
9. integrate the first three real workflows;
10. collect real decision data;
11. build MCP integration;
12. prepare public repository and release documentation.

Further ANE research is allowed only when a product requirement exposes a concrete blocker.
