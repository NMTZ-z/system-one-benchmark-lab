# Local System One

**A local typed-decision control plane for Apple Silicon agents.**

让本地小模型负责 Agent 的高频控制决策，让 LLM 专注真正需要生成、规划和深度推理的工作。

Local System One is not another chatbot and does not replace your LLM. It sits **before or around** an agent's main model and answers small but frequent questions such as:

- Does this task need current Web information?
- Can this request use a cheaper/faster reasoning tier?
- Should this event stay silent, go to a digest, or interrupt the user now?
- Which backend should handle this decision?
- Is a local ANE path healthy enough to use right now?

The project packages a validated **Laya Typed Decisions 421M** runtime, an optional **Apple Neural Engine (ANE)** backend, HTTP/MCP interfaces, a reversible **Hermes plugin**, and a native **DeepSeek Harness adapter**.

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
| **Choice / Score / Noul** | Generic typed decisions for your own control logic | Available through the HTTP API. |

This distinction matters: the project deliberately separates **technical capability** from **what has enough evidence to activate automatically**.

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
GET  /health
GET  /metrics
```

The service binds to loopback by default and does not persist raw task text.

## Optional Apple Neural Engine backend

Install the ANE dependencies:

```bash
python -m pip install -e '.[ane]'
```

Build the validated fixed-shape L512 Core ML package locally:

```bash
scripts/build_typed421_ane.sh
```

Then start Local System One with that package:

```bash
local-system-one \
  --ane-package artifacts/models/typed421-body512-fp16/model.mlpackage
```

The builder pins `laya-coreml` to:

```text
4619e0483f07adf39068532e85b42ec2347edb83
```

Model weights and converted Core ML packages are intentionally **not redistributed** in this repository.

At runtime, the router does not blindly force ANE. It uses token length plus an ANE health gate and falls back to MLX when the accelerator path is unavailable, unhealthy, or unsuitable.

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

The repository also includes a native adapter for the official DeepSeek Harness plugin lifecycle. The first validated target is pinned to `dsh-v0.1.7-rc.2` at commit `477b4f420553e8a52c2fbccc464d7561b239c443`.

Phase 1 intentionally enables only the **Search Gate**:

```text
off -> shadow -> canary
```

The adapter calls Local System One over HTTP, evaluates once per user turn, and can deny only an exact audited set of public-Web tools when a deterministic hard no-Web rule has authority. Model-probability decisions remain Shadow-only. Connection failures and timeouts fail open, and turn-scoped state is cleared before the next turn.

The real validation path used:

```text
DeepSeek Harness -> Nova -> DeepSeek V4.1 Flash
```

Community bundle install for the validated `headless` profile:

```bash
dsh plugin --profile headless add github:NMTZ-z/system-one-benchmark-lab#dsh-plugin
```

The bundle installs in `off` mode by default; enabling Shadow or Canary is an explicit profile override.

See [DeepSeek Harness adapter documentation](integrations/deepseek-harness/local-system-one-dsh/README.md) and the [Phase 0 / Phase 1 probe report](integrations/deepseek-harness/local-system-one-dsh/PHASE0_PROBE.md).

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
- `integrations/deepseek-harness/` — reversible DeepSeek Harness Search Gate adapter
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

Conservative defaults are intentional. A wrong routing decision can be more expensive than the small amount of compute it saves.

## Documentation

Start here depending on what you want to do:

- [Local System One product and API](docs/LOCAL_SYSTEM_ONE_MVP.md)
- [Search Gate](docs/SEARCH_GATE.md)
- [Model Tier Gate](docs/MODEL_TIER_GATE.md)
- [Notification Gate](docs/NOTIFICATION_GATE.md)
- [MCP and launchd deployment](docs/MCP_DEPLOYMENT.md)
- [Hermes plugin productization](docs/HERMES_PLUGIN_PRODUCTIZATION.md)
- [DeepSeek Harness adapter](integrations/deepseek-harness/local-system-one-dsh/README.md)
- [DeepSeek Harness validation report](integrations/deepseek-harness/local-system-one-dsh/PHASE0_PROBE.md)
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