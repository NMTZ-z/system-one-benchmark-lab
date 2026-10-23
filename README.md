# Local System One

**A local typed-decision control plane for Apple Silicon agents.**

让本地小模型负责 Agent 的高频控制决策，让 LLM 专注真正需要生成、规划和深度推理的工作。

Local System One is not another chatbot and does not replace your LLM. It sits **before or around** an agent's main model and answers small but frequent questions such as:

- Does this task need current Web information?
- Can this request use a cheaper/faster reasoning tier?
- Should this event stay silent, go to a digest, or interrupt the user now?
- Is this task actually complete, or should the Agent continue or verify first?
- Which backend should handle this decision?
- Is a local ANE path healthy enough to use right now?

The project packages a validated **Laya Typed Decisions 421M** runtime, an optional **Apple Neural Engine (ANE)** backend, HTTP/MCP interfaces, a reversible **Hermes adapter**, and a native **DeepSeek Harness adapter**. The Runtime is the platform-independent decision plane; each Adapter owns how an abstract decision is safely mapped onto its platform.

## Why this exists

Large language models are good at generating and reasoning, but agents repeatedly spend those expensive calls on tiny routing decisions.

Local System One turns those decisions into a separate local control layer:

```text
User / Agent
     |
     v
Local System One
     |
     +-- hard rules
     +-- typed-decision model
     +-- policy / health gates
     |
     v
LLM / tools / notification / routing action
```

The goal is not "use a small model for everything". The goal is to use a small local model **where a structured decision is enough**, while keeping the system reversible and fail-open.

## What it can decide

| Workflow | Question | Current status |
|---|---|---|
| **Search Gate** | Does this task need public/current Web information? | Functional. Deterministic hard rules can act; model-probability routing remains conservative/Shadow-first. |
| **Model Tier Gate** | Can a bounded task use a faster reasoning tier? | Functional, but broad model-based routing remains experimental. |
| **Notification Gate** | silent / digest / notify_now? | Functional MVP. |
| **Completion Gate** | complete / continue / verify? | **Shadow-only in Phase 8A.** Conservative benchmark completed; Active auto-stop is NO-GO. |
| **Choice / Score / Noul** | Generic typed decisions for your own control logic | Available through the HTTP API. |

This distinction matters: the project deliberately separates **technical capability** from **what has enough evidence to activate automatically**.

**Experimental model providers:** [Model Backend Pilot v1](docs/MODEL_BACKEND_PILOT.md) adds an offline-first, research-only Laya/Jev comparison interface. Default production use remains Laya-only; Jev remote calls and Active Gate execution are not enabled.

## Phase 8.3 — Where is a small model actually useful?

The experimental [Decision Opportunity Contract](docs/PHASE8_3_OPPORTUNITY_CONTRACT.md)
classifies observed decision points as `rule_only`, `typed_model_candidate`,
`native_agent`, or `unsupported`, without changing production Gate behavior.

The [paired evaluation protocol](docs/PHASE8_3_EVALUATION_PROTOCOL.md) separates
native Agent outcomes, Rule-only answers, and Rules + Laya suggestions. Its first
[bounded offline report](docs/PHASE8_3_FINAL_REPORT.md) covers 210 *previously
published* synthetic or public-reconstructed cases with 109 local MLX model calls.
In this limited replay, Retry benefits from Laya on historical synthetic cases.
A follow-on audit identified unequal pre-model Completion rules in the initial
comparison; see the rules-matched controls in the final report before interpreting
Completion accuracy. **These are not fresh blind results, real Agent savings,
Active authorization, or new StepFun E2E.**

### New preregistered synthetic holdout (Phase 8.3)

A separate [80-case pre-model frozen pilot](docs/PHASE8_3_NEW_HOLDOUT_REPORT.md)
uses the same safe B0/C0 hard rules. Completion was 75% vs 75% on 40
author-created cases, and Retry was 90% vs 100% on 40 distinct simulated
failure cases. Actual Laya MLX calls were 29. The data and labeling were
committed before running Laya, but remain synthetic and author-adjudicated:
**this does not prove real-Agent gains, production safety or API savings**.
The [frozen protocol](docs/PHASE8_3_NEW_HOLDOUT_PROTOCOL.md) explains
limits and how no Active permissions were added.

### Native real-provider qualification status (Phase 8.3A)

The [H1/H2/H3 real StepFun native experiment reports](docs/PHASE8_3_REAL_NATIVE_H3_REPORT.md)
now document genuine Hermes read-only tasks on the existing StepFun
Step Plan subscription, not simulated Agent runs:

- [H1 OFF](docs/PHASE8_3_REAL_NATIVE_H1_REPORT.md): native tool and
  independent file proof PASS, but only 2 of 3 attempted physical
  Provider requests reached a recorded terminal result.
- [H2 healthy Shadow](docs/PHASE8_3_REAL_NATIVE_H2_REPORT.md):
  actual Laya/MLX inference twice, exact 2/2 native-to-HTTP HMAC links,
  all three new physical Provider attempts finalized.
- [H3 Runtime-down Shadow](docs/PHASE8_3_REAL_NATIVE_H3_REPORT.md):
  real native file task PASS while the decision Runtime was unavailable;
  two independently correlated HTTP 503 and failed_open events; both
  new physical StepFun requests finalized. Automatic model-backed
  title upgrades were disabled **only in the isolated test Home**.
  Physical request count fell to 2 vs two Agent-reported main calls.
  This supports, but does not uniquely prove, the title-LLM attribution
  for extra physical requests in H1/H2.

**Global: 8/24 physical StepFun requests reserved, 7 HTTP 200 terminal
responses, and 1 H1 historical request still unresolved.** Physical
request billing/credit usage and Agent-level savings are NOT MEASURED.
The original H1 missing response was not retroactively filled;
Phase 8.3A global Provider budget integrity remains **BLOCKED**.
H4 and DSH D1–D4 real tasks have not run. These are scoped real
read-only/Shadow proofs only; **Active/Canary is not authorized**.

**2026-10-22 qualification update:** [H4's negative native read-file
oracle and DSH independent-auth/SDK evidence prerequisites](docs/PHASE8_3_H4_DSH_OFFLINE_QUALIFICATION.md)
have been tested **OFFLINE ONLY**. The actual Hermes read_file tool
returned structured not_found/error fields and the installed tool
observer derived status=error / error_type=tool_error, but no true
H4 StepFun native Agent Retry/Completion observation was run.
DSH OFF/Shadow native SDK control-plane initialization and strict
typed SDK event contracts pass without a credential or main-model
request. DSH real E2E still needs a separate owner-controlled
interactive credential plus a newly frozen bounded native executor.
The same 8/24 physical original StepFun request ledger and its H1
unknown outcome are unchanged.

**2026-10-22 H4 admission incident:** The first frozen H4
failed-read *startup attempt* was refused by the currently running
host Hermes Gateway **before a native Agent Session, tool call or
real StepFun request**. H4 consumed **zero new physical requests**;
the original global request budget remains 8/24. An independent
[H4 Gateway admission incident report](docs/PHASE8_3_H4_GATEWAY_ADMISSION_INCIDENT.md)
documents why this is NOT a native Retry/fail-open result, as well
as a fixed wrapper exit-code propagation bug. Source-only inspection
found an official in-process Hermes one-shot engine that can avoid
the Gateway start path, but it has NOT been run against a Provider.
The H4 attempt is single-shot and will not be overwritten or
automatically retried; any new trial needs its own frozen evidence.

**2026-10-23 reversible H4B source prepared:** A distinct
[H4B pre-registered, owner-safe recovery protocol](docs/PHASE8_3_REAL_H4B_REVERSIBLE_PREREGISTRATION.md)
now replaces the unusable Gateway-backed path with official
in-process Hermes AIAgent behind macOS Seatbelt. The child can
call only the EXACT private native read_file target, can write
only narrowly scoped test-state files, and may connect only to
the existing bounded loopback Provider/observer ports. A durable
test-Home SQLite/plugin/config snapshot and exact process-group
provenance support rollback. A **zero-network sandbox import
rehearsal** passed with test-state digests unchanged. This is
PRE-RUN engineering evidence, NOT a real H4B Agent/StepFun PASS.
No additional physical Provider requests were made by this
source preparation; original H1/H2/H3 ledger remains 8/24
and original H4 remains blocked before the native Agent.

**Real H4B one-shot outcome (2026-10-23):** The frozen reversible
H4B test started its isolated MLX/observer/budget services and a
macOS Seatbelt-protected official in-process Hermes one-shot.
It then **safely FAILED BEFORE constructing AIAgent** because the
sandbox denied the official one-shot's write to /dev/null for
stdout/stderr suppression. **Zero additional StepFun Provider
requests**; the original global tally remains 8/24. All four
H4B-owned process groups stopped, the isolated test Home
SQLite/plugin/config was restored to its original OFF state, and
test auth metadata stayed unchanged. The [independent H4B
incident/rollback report](docs/PHASE8_3_H4B_SEATBELT_ADMISSION_INCIDENT.md)
preserves this as an admission BLOCK, not native tool/Retry PASS.
A later fix allows only /dev/null writes and a zero-network
synthetic run through the official one-shot preamble passed,
but **H4B was not rerun**, its private original was not erased,
and any successor real run needs its own new frozen case.

**2026-10-23 Phase 8.3A H4C new-case preregistration:** The next
[reversible H4C native-failure experiment](docs/PHASE8_3_REAL_H4C_PREREGISTRATION.md)
now has a DIFFERENT run ID, original target manifest, recovery
snapshot, owned PID ledger and HMAC/HTTP paths from both blocked
H4 and H4B. Its test-only MLX/observer/budget helper processes use
an H4C-owned disposable HOME/cache. Original H4B rollback was
independently confirmed, and all H4C source/test Home/physical
budget prerequisites are fail-closed. A local all-network-denied
Hermes one-shot startup rehearsal passed without creating
the H4C original run. This is H4C PRE-RUN preparation only;
real missing-file and Retry Shadow proof must come from the
separate one-shot actual Provider-backed experiment.

The [official isolated test-home handoff](docs/PHASE8_3_OFFICIAL_AUTH_HANDOFF.md)
documents the owner-created standalone Hermes test Home, supported
nonproduction StepFun authentication and strict bounded proxy route.
Raw native messages, credentials, original hidden files and keyed
correlation values are not part of the public repository.

## Quick start

### Requirements

- macOS on Apple Silicon
- Python 3.11–3.13
- Internet access on first model download

Clone and start the default MLX backend:

```bash
git clone https://github.com/NMTZ-z/system-one-benchmark-lab.git
cd system-one-benchmark-lab

python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

local-system-one --host 127.0.0.1 --port 8787
```

The default source alias is `laya-typed-decisions`. It resolves the validated checkpoint revision:

```text
convaiinnovations/laya-typed-decisions
f9ab0b228f0fc0f14d873dbc99038f135c2da1b2
```

Check the service:

```bash
curl http://127.0.0.1:8787/health
```

Available endpoints include:

```text
POST /v1/choice
POST /v1/score
POST /v1/noul
POST /v1/workflows/search-gate
POST /v1/workflows/model-tier-gate
POST /v1/workflows/notification-gate
POST /v1/workflows/completion-gate
GET  /health
GET  /metrics
```

The service binds to loopback by default and does not persist raw task text.

## Optional Apple Neural Engine backend

Install the ANE dependencies:

```bash
python -m pip install -e '.[ane]'
```

Download the validated fixed-shape L512 Core ML package from Hugging Face:

```bash
hf download NMTZ/laya-typed-decisions-421m-coreml-ane \
  --include 'L512/*' \
  --local-dir artifacts/models/laya-typed421-ane
```

Then start Local System One with the downloaded package:

```bash
local-system-one \
  --ane-package artifacts/models/laya-typed421-ane/L512/model.mlpackage
```

The Hugging Face release also includes the validated L192, L384 and L640 research variants. L512 remains the recommended default because it covered 1,966 / 2,000 frozen benchmark decisions while preserving 99.8% selected-decision agreement with the MLX reference.

If you prefer to reproduce the conversion locally, build the same validated fixed-shape L512 package with:

```bash
scripts/build_typed421_ane.sh
```

Then start Local System One with the locally built package:

```bash
local-system-one \
  --ane-package artifacts/models/typed421-body512-fp16/model.mlpackage
```

The builder pins `laya-coreml` to:

```text
4619e0483f07adf39068532e85b42ec2347edb83
```

The original 421M checkpoint is not duplicated by this project. The converted fixed-shape ANE artifacts are published separately at [`NMTZ/laya-typed-decisions-421m-coreml-ane`](https://huggingface.co/NMTZ/laya-typed-decisions-421m-coreml-ane), with provenance, SHA256 metadata and benchmark evidence. The Hugging Face packages are ANE transformer-body artifacts and still use the pinned upstream Laya checkpoint for tokenizer, embedding lookup and the host-side action head.

At runtime, the router does not blindly force ANE. It uses token length plus an ANE health gate and falls back to MLX when the accelerator path is unavailable, unhealthy, or unsuitable.

## Unified Adapter Contract

Hermes and DeepSeek Harness now implement **Adapter Contract v1**. The shared
contract defines decision semantics, modes, action outcomes, fail-open meaning,
and comparable privacy-safe telemetry without standardizing platform internals.

```text
Local System One Runtime
        |
        v
Decision Contract v1
   /             \
Hermes Adapter   DSH Adapter
```

`ModelTier=fast` is a portable decision. `reasoning_effort=low`, a provider/model
allowlist, or a concrete Web tool name is not. Those stay inside the relevant
Adapter.

See [Adapter Contract v1](docs/ADAPTER_CONTRACT.md) and the
[machine-readable schema](contracts/adapter-contract-v1.schema.json).
Completion is a backward-compatible Contract v1 extension; see
[Completion Gate](docs/COMPLETION_GATE.md) for semantics, bounded context,
benchmark evidence, and the Active NO-GO decision.

## Hermes integration

The repository includes a native Hermes plugin with three modes:

```text
off -> shadow -> canary
```

First install is inert by default.

For an evaluation profile:

```bash
scripts/install_hermes_system_one_plugin.sh systemoneeval
scripts/set_hermes_system_one_mode.sh systemoneeval shadow
scripts/hermes_system_one_status.sh systemoneeval
```

Shadow mode observes decisions without changing the provider request. Canary requires explicit acknowledgement and remains deliberately narrow.

Rollback is built in:

```bash
scripts/uninstall_hermes_system_one_plugin.sh systemoneeval
```

The plugin is designed to **fail open**: if Local System One is unavailable or a recommendation is incomplete, Hermes keeps its original request unchanged.

See [Hermes plugin documentation](integrations/hermes/local-system-one-hermes/README.md) for the full lifecycle and safety constraints.

## DeepSeek Harness integration

The repository includes `local-system-one-dsh`, a native adapter for the official DeepSeek Harness plugin lifecycle. It now covers **Search Gate + Model Tier Gate + Notification Gate (Shadow) + Completion Gate (Shadow)** alongside Hermes; Unified Adapter Contract v1 gives both platforms one versioned semantic contract while preserving platform-specific execution and reversible, fail-open behavior.

Validated DSH targets are deliberately exact:

```text
0.1.7-rc.2  @ 477b4f420553e8a52c2fbccc464d7561b239c443
0.2.1-alpha.1 @ 5badb15009ae1756c3afe0ae0cef1faafc290ccc
```

The adapter supports independent Search, Model Tier, Notification, and Completion observation. Search and Model Tier run at turn start; Notification and Completion observe the completed Agent turn and remain Shadow-only. Search Canary retains the audited hard no-Web rules. Model Tier Canary is experimental and disabled by default; when explicitly acknowledged and enabled, only an audited deterministic hard-fast decision on an exact verified provider/model route may copy the first provider request and change `reasoningEffort: high -> low`. Model/probability decisions never receive active authority.

Real provider-wire validation paths include:

```text
DeepSeek Harness -> Nova -> DeepSeek V4.1 Flash
DeepSeek Harness -> StepFun Step Plan -> step-5-preview
```

The StepFun route completed native high/low requests and an automatic Local System One high-to-low Canary transition, including tool-loop restoration to high after the first provider call.

The installation bundle remains inert in `off` mode. Connection errors, timeouts, malformed gate responses, unsupported provider/model routes, and any missing Canary authority fail open to native DSH behavior. Turn-scoped Search and Model Tier state is cleared at turn end.

Community bundle install for a supported `headless` profile:

```bash
dsh plugin --profile headless add github:NMTZ-z/system-one-benchmark-lab#dsh-plugin
```

See [DeepSeek Harness adapter documentation](integrations/deepseek-harness/local-system-one-dsh/README.md), the [Phase 0 / Phase 1 probe report](integrations/deepseek-harness/local-system-one-dsh/PHASE0_PROBE.md), and the [Phase 7A Model Tier parity report](integrations/deepseek-harness/local-system-one-dsh/PHASE7A_MODEL_TIER_PARITY.md).

## Architecture

```text
Agent / Hermes / DeepSeek Harness / MCP client
          |
          v
  Local System One API
          |
          v
   Decision Engine
    /    |     \
 rules  policy  typed model
          |
          v
       Router
      /      \
    MLX      L512 ANE
     ^          |
     +-- health/fallback
```

Main components:

- `local_system_one/` — service, router, health gate, runtime adapters and workflows
- `integrations/hermes/` — reversible Hermes native plugin
- `integrations/deepseek-harness/` — reversible DeepSeek Harness multi-Gate adapter
- `scripts/` — local service, ANE build, launchd and plugin operations
- `docs/` — design notes and product validation
- `results/reports/` — frozen public benchmark reports

## Verified results

The repository grew out of a reproducible JEV/Laya/ANE evaluation program. A few results matter directly to the product:

### Typed Decisions quality

On the public 400-case / 2,000-decision benchmark:

| Backend / model | Accuracy |
|---|---:|
| Laya Typed Decisions 421M MLX | **0.766** |
| Jev 1.13.0 | **0.737** |

These numbers describe this benchmark only; they are not a general model ranking.

### L512 ANE engineering

For the validated 421M fixed L512 path:

- natural benchmark coverage: **1,966 / 2,000 decisions (98.3%)**
- selected-decision agreement vs same-subset MLX: **99.8%**
- representative gross system energy per decision: about **2.07× better than MLX**
- L640 reaches 100% capacity coverage, but was not the best default latency/efficiency tradeoff

The key result is **energy-efficient local inference with runtime health gating**, not a claim that ANE is universally faster for every request.

### Reproducibility

The public release path has been validated from an isolated sanitized bundle:

- clean Python installation
- pinned model acquisition
- pinned `laya-coreml` checkout
- fresh L512 conversion
- Runtime startup probe
- old-vs-rebuilt output parity checks

See [Public release notes](docs/PUBLIC_RELEASE.md).

## Current limitations

This is an **alpha control-plane project**, not a universal autonomous router.

Important limits:

- Search model probabilities are **not** trusted as unrestricted final authority.
- Model Tier broad automatic downgrade is **not** proven to provide a stable latency benefit.
- The ANE backend uses a fixed L512 body and must fall back when requests do not fit or health checks fail.
- Notification preferences are not personalized yet.
- Hermes Canary is intentionally narrow and requires explicit acknowledgement.
- A second physical Mac would strengthen cross-machine reproducibility evidence, although the clean public-path rebuild already passes on the development M4 Mac mini.
- Phase 8.2B's verified native-Hermes/DSH request correlations are **bounded localhost-Mock tests**; real StepFun post-change billing, Laya/MLX quality, robust overhead and Active behavior have not been requalified.

Conservative defaults are intentional. A wrong routing decision can be more expensive than the small amount of compute it saves.

## Documentation

Start here depending on what you want to do:

- [Local System One product and API](docs/LOCAL_SYSTEM_ONE_MVP.md)
- [Unified Adapter Contract v1](docs/ADAPTER_CONTRACT.md)
- [Phase 8.2B Evidence Contract and privacy-safe native correlation](docs/PHASE8_2B_EVIDENCE_CONTRACT.md)
- [Phase 8.2B Budget Ledger and reconciliation](docs/PHASE8_2B_BUDGET_LEDGER.md)
- [Phase 8.2B scoped native Mock E2E report](docs/PHASE8_2B_FINAL_REPORT.md)
- [Search Gate](docs/SEARCH_GATE.md)
- [Model Tier Gate](docs/MODEL_TIER_GATE.md)
- [Notification Gate](docs/NOTIFICATION_GATE.md)
- [MCP and launchd deployment](docs/MCP_DEPLOYMENT.md)
- [Hermes plugin productization](docs/HERMES_PLUGIN_PRODUCTIZATION.md)
- [DeepSeek Harness adapter](integrations/deepseek-harness/local-system-one-dsh/README.md)
- [DeepSeek Harness validation report](integrations/deepseek-harness/local-system-one-dsh/PHASE0_PROBE.md)
- [DeepSeek Harness Phase 7A Model Tier parity](integrations/deepseek-harness/local-system-one-dsh/PHASE7A_MODEL_TIER_PARITY.md)
- [Phase 7B Notification + StepFun validation](integrations/deepseek-harness/local-system-one-dsh/PHASE7B_NOTIFICATION_STEPFUN.md)
- [Public release / reproducibility](docs/PUBLIC_RELEASE.md)
- [Upstream provenance](references/UPSTREAM.md)

For the underlying experiments:

- [Jev Typed Decisions benchmark](results/reports/M4-Jev-1.13.0-Typed-Decisions-v0.1.md)
- [Laya 421M quality benchmark](results/reports/M4-Typed-Decisions-Quality-Laya-v0.1.md)
- [Core ML vs MLX parity](results/reports/M4-Typed-Decisions-421M-CoreML-vs-MLX-Quality-Parity-v0.1.md)
- [Phase 4 ANE engineering](results/reports/Phase4-421M-ANE-Engineering-Final-v1.0.md)

## Project philosophy

System One is useful here as an **agent control primitive**, not as a replacement for a general-purpose LLM.

The practical pattern is:

```text
hard rule when certainty is available
        ->
small local probabilistic decision when useful
        ->
policy / confidence / health gate
        ->
LLM or action
```

That makes the control layer cheap, local, inspectable, reversible, and easy to disable.

## License

Local System One is released under the [Apache License 2.0](LICENSE).

The project depends on and documents upstream work separately. See [references/UPSTREAM.md](references/UPSTREAM.md) for pinned revisions and provenance.
