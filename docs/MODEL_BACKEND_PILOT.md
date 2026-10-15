# Model Backend Pilot v1

**Status:** engineering implementation under review; real Jev API integration
is **BLOCKED until explicitly authorized**. The pinned API parser and HTTP
transport have Mock coverage; Mock success is not Jev live success.

Base: GitHub main commit b9a497402411b6f0492787860e54ed8f44cfb3b4,
merged PR #5 (Phase 8C, Shadow-only). Independent worktree/branch:
feat/model-backend-pilot-v1. No 8C.1 code or production Agent profile is changed.

## Purpose and scope

Run Rule-only, Rules+Laya and Rules+Jev on **the same frozen public synthetic
input** without changing any existing Gate's hard rules or claiming a winner
before evidence exists. This pilot adds a provider-neutral Typed Decision
boundary, not a production hot-switch, a third platform adapter, an Active
recovery gate or an automatic paid cloud fallback.

### Audit

The existing DecisionRuntime.predict() returns Laya-compatible wire answers
and requires token_count(). DecisionEngine couples that to MLX/ANE routing,
startup probes, health metrics and ANE -> MLX fallback. It should **not** be
reinterpreted as a model-neutral provider interface. Existing Completion and
Retry gates already share DecisionEngine.decide(), so the pilot uses a
research-only ResearchEngine facade instead of duplicating their rules.
The original Local System One service/CLI and Adapter Contract v1 stay unchanged.

The research CLI is import-safe for Jev: laya_mlx and laya_coreml are imported
only inside the selected Laya construction branch. Jev never instantiates a
Laya runtime or downloads a checkpoint.

## Quick use from repository root

The following offline commands were validated with Python 3.12 on the project
Mac. Install existing development requirements before using another machine.

Rule-only baseline:

~~~bash
python -m benchmarks.model_backend_pilot run \
  --provider rule \
  --dataset benchmarks/model_backend_pilot/public_synthetic_v1.jsonl \
  --output /tmp/model-backend-rule.json
~~~

Rule-only returns **exit code 2** because the three direct primitive cases have
no deterministic Rule-only equivalent and are correctly marked
unsupported. Hard-rule and fallback cases are still recorded. This exit code
does not imply an API failure.

Existing Laya/MLX checkpoint, unchanged defaults:

~~~bash
python -m benchmarks.model_backend_pilot run \
  --provider laya \
  --dataset benchmarks/model_backend_pilot/public_synthetic_v1.jsonl \
  --output /tmp/model-backend-laya.json
~~~

The source alias is pinned by runtime/sources.py. Use
--laya-source and --laya-model-identity together for another local checkpoint.
--ane-package optionally uses the **existing** ANE startup probe and fallback.
An ANE-to-MLX fallback must be counted as MLX execution, never as ANE success.

**Jev is network-disabled by default.** This command intentionally fails
without contacting TypeSafe:

~~~bash
python -m benchmarks.model_backend_pilot run \
  --provider jev \
  --dataset benchmarks/model_backend_pilot/public_synthetic_v1.jsonl \
  --output /tmp/model-backend-jev.json
~~~

For a separately approved, public/synthetic-only Jev experiment, an operator
must set TYPESAFE_API_KEY through an appropriate secret source (never in CLI
arguments) and explicitly enable ALL of the following: --allow-remote,
--public-data-confirmed, --max-requests, --max-input-bytes, --max-usd and
--timeout. The pinned --model defaults to jev-1.13.0; use only a verified
concrete version, not jev-latest/jev-preview aliases. **This is documentation
of the required controls, not authorization to perform a live call.**

After three genuine result files exist, compare with:

~~~bash
python -m benchmarks.model_backend_pilot compare \
  --reports /tmp/model-backend-rule.json /tmp/model-backend-laya.json /tmp/model-backend-jev.json \
  --output /tmp/model-backend-comparison.json
~~~

Compare rejects mixed dataset/strategy/code hashes, missing/duplicate/reordered
case IDs, version drift, and a Jev result lacking real remote attempts.

## TypeSafe API and network safety

References verified 2026-10-15:
https://docs.typesafe.ai/api and https://docs.typesafe.ai/models

- POST https://api.typesafe.ai/v1/systemone (fixed HTTPS host, certificate
  verification, no redirects). Model, state and question map are explicit.
- Stable jev-latest currently points to jev-1.13.0; jev-preview currently
  points to jev-1.14.0. This pilot defaults to the pinned 1.13.0.
- Credential lookup is TYPESAFE_API_KEY only; no key is logged or persisted.
- External calls require explicit remote enablement, data classification
  confirmation, request-count bound, input-byte bound, USD estimate budget
  and bounded timeout. Zero automatic HTTP retries. Network/protocol failure
  remains a **failure**, with Gate-specific safe fallback advisory only.
- Responses are size-bounded (64KiB). HTTP failure bodies are never logged.
  Request IDs and primitive types must match; returned model must equal the
  requested *concrete* version.
- Price basis: USD 0.042 per million **input tokens** (verify before any
  future paid run). The reservation based on request byte length is a
  conservative *planning estimate*, **not a contractual billing cap**.
  The usage-derived cost estimate is not the verified billing invoice.
  Actual billing and errors with unavailable usage remain uncertain.
- Absolutely no NAS private raw logs, production transcripts, prompt history,
  credentials, or unapproved real-world observations may be sent. Synthetic
  test descriptions are included in the public dataset only.

## Frozen evaluation method

public_synthetic_v1.jsonl contains 12 small, public, non-blind demonstration
items: three primitive cases, four Completion cases and five Retry cases.
The results record:

- dataset SHA256, run code SHA, experiment policy identifier;
- case IDs, ground truth, status/failure and usable decision;
- requested/resolved model, actual execution backend and client wall time;
- model participation, valid-only vs all-requests metrics and failures;
- Score MAE / within-one-level separately from discrete accuracy;
- Completion premature-stop errors and complete recall;
- Retry unsafe raw advice, unsafe guarded advice, missed verification;
- account token usage when supplied; no fabricated local/remote usage;
- explicit warning that latency is user-side wall clock, not identical-hardware
  inference time; Shadow results do not establish actual Agent token savings.

Deterministic Gate rules run **before** either model. Models never add new
permitted candidates. Completion's existing 0.70 threshold is reused as a
labeled **experimental common policy**; it is not Jev production calibration.
The Rule-only Completion baseline conservatively defaults to continue when no
hard condition resolves an outcome. Unsupported direct primitive cases remain
in the audit denominator instead of disappearing.

A 12-item synthetic harness proves plumbing, not performance in the field.
Historical benchmark runs are regression context, not newly independent blind
tests. No general Jev-vs-Laya quality claim is justified from this pilot alone.

## Status and acceptance gates

- Core Engineering: see tests/test_model_backend_pilot.py and main Python suite.
- Laya Non-regression: original inference code untouched; real MLX and
  old-vs-wrapper comparison should be separately reported.
- Jev Live Integration: **BLOCKED**, until specific remote data/cost authorization
  and genuine response evidence are available.
- Comparative Evaluation: **PARTIAL**, since Jev is not live.
- Real-world Model Advantage: **NOT_ESTABLISHED**.
- Production / Active Activation: **NOT_AUTHORIZED**.

Nothing here modifies launchd, default 127.0.0.1:8787 server, Hermes Catalog,
DeepSeek Harness install branch, or OFF/Shadow/Canary permissions. This is an
additive **research interface only**.
