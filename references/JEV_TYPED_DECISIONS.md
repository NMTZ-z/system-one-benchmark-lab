# Jev 1.13.0 — Typed Decisions external reference

Last verified: 2026-09-23

This file records **external public evidence** used to contextualize the local
SystemOne Benchmark Lab runs. These numbers are not presented as measurements
performed by this repository.

## API contract

Official TypeSafe Swagger documentation:

- API root: `https://api.typesafe.ai`
- decision endpoint: `POST /v1/systemone`
- model-discovery endpoint: `GET /v1/models`
- authentication: `Authorization: Bearer <API_KEY>`

Source:
`https://api.typesafe.ai/docs`

A direct unauthenticated request from the M4 benchmark host on 2026-09-23
returned HTTP 403 with an authentication error requiring an API key.

The local adapter never writes the API key into benchmark output. Credential
resolution order:

1. environment variable `TYPESAFE_API_KEY`;
2. macOS Keychain generic-password service `typesafe-systemone`, using the
   current macOS account by default.

The benchmark records only the non-secret credential source label
(`env:TYPESAFE_API_KEY` or `keychain:typesafe-systemone/<account>`).

Files:

- adapter: `adapters/jev.py`
- secure interactive Keychain helper: `scripts/configure_typesafe_keychain.sh`

## Public Typed Decisions measurement

The public `LocalLLaMA/typed-decisions` dataset card reports a TypeSafe Jev
measurement taken on 2026-09-18 through `POST /v1/systemone`.

The request used `model: jev-latest`; the response reported the concrete model
as `jev-1.13.0`.

Reported scope:

- mode: **general / zero-shot**
- cases: 400
- decisions: 2,000
- errors: 0

Reported metrics:

| Metric | Jev 1.13.0 external measurement |
|---|---:|
| Accuracy | 0.727 |
| Soft accuracy | 0.580 |
| Macro F1 | 0.613 |
| KL from gold | 1.442 |
| Total variation | 0.251 |
| Brier | 0.148 |
| ECE | 0.144 |
| Score MAE | 0.391 |
| Within 1 level | 0.952 |
| End-to-end P50 / case | 710 ms |

The dataset card reports a total API cost of USD 0.016 for that run at the
then-published TypeSafe price.

Source:
`https://huggingface.co/datasets/LocalLLaMA/typed-decisions/blob/main/README.md`

## Comparability warning

Jev and Laya Typed Decisions 421M are not trained under the same regime.

The local Laya checkpoint is a **specialist** fine-tuned on the benchmark's
1,200-case training split / 6,000 decisions from the same four workflows.

Jev is reported as a **generalist zero-shot** model that answered the benchmark
question schemas without task-specific fitting.

Therefore side-by-side metrics are useful for understanding different tradeoffs,
but must not be turned into an overall model-quality ranking.

Latency is also not a controlled comparison:

- Jev is a remote hosted API measurement.
- Laya MLX/Core ML are local M4 measurements.
- network geography, service hardware, first-use compilation, and batching are
  different.

## Local independent rerun status

The local Jev runner is implemented and ready.

Recommended one-time macOS setup:

```bash
./scripts/configure_typesafe_keychain.sh
```

The script delegates secret entry to the macOS `security` CLI with interactive
password input, so the key is not echoed and does not appear in the command
line. After the Keychain item exists, run:

```bash
PYTHONPATH=references/laya-coreml .venv/bin/python \
  -m benchmarks.quality.run_typed_decisions \
  --backend jev \
  --model jev-latest \
  --output results/raw/typed-decisions-quality-jev-1.13.0.json
```

An explicit `TYPESAFE_API_KEY` environment variable remains supported and
takes priority over Keychain.

Do not place the API key in shell history, Git, benchmark JSON, report text, or
chat messages.

## Local independent rerun completed

A full local rerun was completed on 2026-09-23/24 (+08:00):

- request alias: `jev-latest`
- concrete model returned by all completed responses: `jev-1.13.0`
- 400 / 400 cases
- 2,000 / 2,000 decisions
- zero API errors
- accuracy: 0.737
- Brier vs soft gold: 0.14774
- KL from gold: 1.50336
- Score MAE: 0.38757
- P50 end-to-end latency from this client: 960.1 ms/case

The test parquet at the public Sep 18 measurement commit and at the locally
pinned revision has the same SHA-256:
`4f294f218ea1da27f3efef936359389c62ea4d3973a41457732990f1d31b647c`.

A 100-case immediate repeat changed 9 / 500 selected labels (1.8%), so the live
endpoint is not bitwise deterministic under the observed conditions. This is
recorded in the local report rather than treating any single run as an immutable
score.

Local report:
`results/reports/M4-Jev-1.13.0-Typed-Decisions-v0.1.md`
