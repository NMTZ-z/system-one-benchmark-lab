# Model Backend Pilot v1

**Status:** research engineering and real Jev 1.13.0 API pilot **PASS** on the
public 12-case synthetic corpus as of 2026-10-16. Production/Active use is
**NOT AUTHORIZED**. PR #6 remains subject to independent code review. This
is a verified live API run, not a declaration of real-world model superiority.

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

### Final Integrity Hardening: trusted execution and evidence

**A run must start from its own Git checkout root.** The CLI verifies that
Git is present, the checkout root matches this project, and a committed HEAD
exists, then captures the revision and clean/dirty state **before provider
initialization**. An independent sanitized `PUBLIC-RELEASE.json` source bundle
has no authenticated Git checkout; it currently fails closed with a controlled
preflight error, including for Rule-only. Run research from an actual Git
checkout instead. Supporting exported archives requires a separately audited
bundle-content verification mechanism; a manifest containing only a commit
string is not sufficient. Dirty-source runs can be recorded for diagnosis but
are rejected by `compare`.

Before any billable API calls, the research CLI validates the entire dataset,
including *all* Choice/Score/Noul and Completion/Retry payloads and legal gold
labels, the remote authorization/budget knobs, and the output path's ability
to create a temporary file. Invalid late rows cannot generate earlier paid
requests. Writes are staged to a temporary file in the target directory and
atomically replace only the intended output. Input datasets and reports cannot
be overwritten via same path, symbolic link or hard link.

For every non-Score observation, `correct` is **derived** from
`status == "ok"` and the typed `gold` vs `decision` comparison; report
validation rejects contradictions before recomputing summaries. Three-way
comparison checks that all providers share the same case IDs, family, primitive,
gold label, unsafe labels and verification requirement, rather than assuming
that three claimed dataset SHA-256 strings authenticate the underlying cases.
This is integrity checking of supplied experiment evidence, **not a digital
signature or proof against coordinated fabrication of all source reports**.

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

The source alias is pinned by runtime/sources.py. **Source normalization
precedes identity selection:** an existing local directory takes precedence
(even when named `laya-typed-decisions` or the official model ID), and
therefore requires an explicit `--laya-model-identity`. A caller-supplied
identity labels a local checkpoint but is not itself a cryptographic proof
of checkpoint immutability. No local directory may be silently labeled as
the official pinned revision. The `run` CLI also refuses to use the input
dataset as its output, even when the two paths are aliases through a
symbolic link or a POSIX hard link, preserving the frozen data bytes.
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
must provide a TypeSafe credential via TYPESAFE_API_KEY or the existing
macOS Keychain service `typesafe-systemone` (never in CLI arguments), and
explicitly enable ALL of the following: --allow-remote,
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
Comparison output paths resolving to an input report (including symlinks)
**or sharing an inode through a POSIX hard link** are rejected before
writing. This protects the original experimental evidence files. All three
input reports must be JSON objects with a compatible v1 schema, required
run identity, clean-checkout evidence, valid case records and matching
summary totals; malformed inputs cause a controlled CLI validation error
rather than an uncaught traceback. In addition, the comparison recalculates
**all aggregate metrics** from each report's validated case records and
rejects any discrepancy (including nested by-family counts, extra keys,
wrong types, inflated accuracy or safety counts). Non-Score `correct`
flags are checked against the original gold/decision/status evidence before
recomputing statistics. Every successful model-sourced case must have a
nonempty requested/resolved model identity equal to the run's single pinned
model ID, plus its actual execution backend; version claims on other cases
must not drift either. For Jev, the pinned model must be a concrete
`jev-X.Y.Z` version and its recorded remote attempts cannot be less than
the number of successful model-backed decisions, exceed one attempt per
sample, or exceed the total of successful model decisions plus recorded
provider-error cases (zero automatic retries). The unknown-usage count must
be consistent with remote attempts, while known token usage requires valid
nonnegative integer input/output token fields. Rule-only and Laya results
cannot claim remote attempts. Only freshly recomputed metrics are placed into
the combined comparison output.

## TypeSafe API and network safety

References rechecked 2026-10-16:
https://docs.typesafe.ai/api and https://docs.typesafe.ai/models

- POST https://api.typesafe.ai/v1/systemone (fixed HTTPS host, certificate
  verification, no redirects). Model, state and question map are explicit.
- Stable jev-latest currently points to jev-1.13.0; jev-preview currently
  points to jev-1.14.0. This pilot defaults to the pinned 1.13.0.
- Credential lookup prefers `TYPESAFE_API_KEY`; on macOS it falls back to
  the existing Keychain generic-password entry `typesafe-systemone` for the
  current OS user. Keychain retrieval is disabled until explicit
  remote/data/budget controls are satisfied. No key is logged or persisted.
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
  Valid server usage is counted even when model/version/answer validation fails.
  `remote_usage_unknown_attempts` counts requests without reliable usage,
  including HTTP failures; these are not treated as zero actual spend.
- Absolutely no NAS private raw logs, production transcripts, prompt history,
  credentials, or unapproved real-world observations may be sent. Synthetic
  test descriptions are included in the public dataset only.

## Frozen evaluation method

public_synthetic_v1.jsonl contains 12 small, public, non-blind demonstration
items: three primitive cases, four Completion cases and five Retry cases.
Before provider instantiation or billable requests, all cases are validated
with the same typed request/Gate parsers used during the run. Score cases in
particular require complete ordered level descriptions and a finite **numeric**
gold value inside the score level range (numeric strings, booleans and
out-of-range values are invalid). All malformed labels and request payloads
fail before the provider can read credentials or send any billable request.
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
- unsafe raw model advice still counts when later rejected by the legacy Gate;
  failed inferences are not silently dropped from safety accounting.

Deterministic Gate rules run **before** either model. Models never add new
permitted candidates. Completion's existing 0.70 threshold is reused as a
labeled **experimental common policy**; it is not Jev production calibration.
The Rule-only Completion baseline conservatively defaults to continue when no
hard condition resolves an outcome. Unsupported direct primitive cases remain
in the audit denominator instead of disappearing.

A 12-item synthetic harness proves plumbing, not performance in the field.
Historical benchmark runs are regression context, not newly independent blind
tests. No general Jev-vs-Laya quality claim is justified from this pilot alone.

## Frozen baseline evidence (2026-10-15)

Published per-case, public-synthetic outputs (without source task text):
`results/processed/model-backend-pilot-rule-v1.json` and
`results/processed/model-backend-pilot-laya-v1.json`.

- Experiment source SHA: `be1bf1a5469402f1e3361229107c28151ff14f6b` (clean checkout).
- Dataset SHA-256: `215c35e52e0c1abbe1c3219f7d24828db1fe9298d43cb2e2b5baf27c9c176c90`.
- Rule-only: 9/12 valid outcomes; 3 direct primitive cases explicitly
  `unsupported`. Discrete classification: 7/11 (63.6%) **all requests**,
  or 7/9 (77.8%) among valid results. There is no score prediction.
- Rules + real Laya/MLX: 12/12 valid. Discrete classification: 9/11
  (81.8%), one Score absolute error 0.1777. Six samples called Laya;
  six were handled by rules. Model-invoked client P50: **57.7 ms**.
- Both approaches had zero dangerous *guarded* suggestions on these twelve
  synthetic cases. Laya produced one potentially unsafe **raw Completion**
  suggestion (C04: `complete` for a case labeled `verify`), downgraded to
  `verify` by the unchanged Completion threshold. Laya recalled zero out of
  one gold `complete` samples; a missed completion is NOT an early-stop error.
- Real Laya paired old-vs-wrapper checks on Choice, Score and Noul agreed
  in decision, raw probabilities and execution backend; three inputs only.
- Python tests: 523 passed. DSH Vitest: 55 passed; typecheck/build passed.
- The Laya checkpoint triggers an MLX temperature-clamping warning for an
  affected Choice bucket; do **not** treat those probabilities as calibrated.
- As of **this earlier 2026-10-15 frozen snapshot**, Jev was **NOT_RUN** live.
  The 2026-10-16 paired, real-API experiment below supersedes that status;
  this earlier run is retained without silently replacing historical evidence.

Scores are illustrative, not independent blind estimates or evidence of
real-world quality. This 12-case frozen corpus is available for inspection,
not suitable for statistically meaningful cross-model rankings.

## Paired real-API pilot evidence (2026-10-16)

After fixing PR #6's two second-round Codex P2 findings, the isolated research
code was frozen and committed as
`935c58f19b8ccf6817b7e7561276b7141e9549e3`. All three provider runs were
made against that **same clean checkout**, frozen dataset SHA-256
`215c35e52e0c1abbe1c3219f7d24828db1fe9298d43cb2e2b5baf27c9c176c90`,
and experimental Gate policy `frozen-original-gate-policy-v1`.
The `compare` command verified source/data/strategy consistency, sample IDs,
actual requested/resolved models and the clean checkout evidence.

The four result JSONs are saved as public-synthetic-only artifacts:

- `results/processed/model-backend-pilot-20261016-rule.json`
- `results/processed/model-backend-pilot-20261016-laya.json`
- `results/processed/model-backend-pilot-20261016-jev.json`
- `results/processed/model-backend-pilot-20261016-comparison.json`

| Metric | Rule-only | Rule + Laya / MLX | Rule + Jev / remote HTTP |
| --- | ---: | ---: | ---: |
| Valid cases | 9 / 12 (3 unsupported primitives) | 12 / 12 | **12 / 12** |
| Discrete accuracy (all 11 classification requests) | 7 / 11 (63.6%) | 9 / 11 (81.8%) | **11 / 11 (100%)** |
| Score absolute error (1 case) | N/A | 0.1777 | **0.01** |
| Model-invoked cases | 0 | 6 | 6 |
| Early `complete` errors | 0 | 0 | 0 |
| `complete` recall (1 gold case) | 0 / 1 | 0 / 1 | 1 / 1 |
| Unsafe raw suggestions | 0 | 1 | 0 |
| Unsafe guarded suggestions | 0 | 0 | 0 |
| Client wall-clock P50 of model-invoked cases | N/A | 61.3 ms | 1481.2 ms |

**Jev live evidence:** On the explicitly approved 2026-10-16 test, a single
synthetic Noul smoke probe returned `jev-1.13.0` with 285 input tokens and
20 output tokens. The separate twelve-case run made exactly **6 real HTTPS API
requests**, since the unchanged Gate rules resolved the other six cases
without a model. All six returned actual model `jev-1.13.0`, valid typed
answers and usage; there were zero API errors and **zero unknown-usage
attempts**. Those six calls reported **2,397 input tokens**, corresponding
to **USD 0.000100674** *usage-derived estimated charges* at the published
rate. The initial smoke accounted for another 285 input tokens
(approximately USD 0.00001197 by the same estimator). This is **not a verified
TypeSafe invoice**. Remote budget control during the paired run was a maximum
of 12 requests, 4,096 body bytes/request, USD 0.01 estimated spend and an
8-second timeout; no retries or arbitrary destinations. Only the prepublished
synthetic data were sent; the API key was read from the existing macOS Keychain
and was never logged or exported.

**Interpretation limits:** The tiny demonstration corpus was designed to
exercise the integration, with only 1 gold `complete` and 1 Score sample.
Although Jev outscored Laya on this specific set, the data cannot establish
that Jev is generally better, calibrated, safer or more cost-effective. Local
MLX vs network HTTPS latencies represent different hardware and geography.
Neither real Agent provider-backed E2E nor ANE parity is established. Production
permissions are unchanged. The Laya temperature-clamping warning remains
relevant to any confidence-dependent claim.

## Status and acceptance gates

- **Core Engineering: PASS**, code/version/input integrity and full tests.
- **Laya Non-regression: PASS**, scoped to actual MLX test cases; ANE-specific
  model parity not evaluated under this pilot.
- **Jev Live Integration: PASS**, for pinned `jev-1.13.0`, Choice/Score/Noul,
  plus Completion/Retry through the unchanged experimental Gate rules.
- **Comparative Evaluation: COMPLETE (pilot synthetic 12-case scope only)**;
  external independent-blind evaluation and real Agent E2E remain **PARTIAL**.
- **Real-world Model Advantage: NOT_ESTABLISHED**.
- **Production / Active Activation: NOT_AUTHORIZED**.

This acceptance establishes that *two real decision providers can be invoked,
validated and compared fairly under shared rules*. It does **not** license
automatic model switching, cloud fallback, action execution or paid escalation.
PR #6 must still complete subsequent independent code-review gates before merge.


Nothing here modifies launchd, default 127.0.0.1:8787 server, Hermes Catalog,
DeepSeek Harness install branch, or OFF/Shadow/Canary permissions. This is an
additive **research interface only**.
