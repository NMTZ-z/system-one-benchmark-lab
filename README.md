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

**Release baseline:** this branch is a v0.2.0 RC candidate, subject to the checks in the release manifest. Hermes installs OFF and first Shadow enables Search only unless the profile already contains explicit Gate choices. Canary can mutate requests; production Active and Canary are not authorized. See the [v0.2.0 scope](docs/V0_2_PRODUCT_SCOPE.md) and [release baseline](docs/PHASE8_4A_RELEASE_BASELINE.md).

The repository also retains Phase 8.3 Benchmark Lab source and evidence. Historical H4 executors are frozen and require separate authorization to run. They are not part of the product source bundle or Python wheel; see the [integration review](docs/PHASE8_4A_INTEGRATION_REVIEW.md).

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
| **Retry / Escalation Gate** | How should a failed tool operation be assessed? | Shadow-only advisory; no automatic retry or model escalation. |
| **Choice / Score / Noul** | Generic typed decisions for your own control logic | Available through the HTTP API. |

This distinction matters: the project deliberately separates **technical capability** from **what has enough evidence to activate automatically**.

**Experimental model providers:** [Model Backend Pilot v1](docs/MODEL_BACKEND_PILOT.md) adds an offline-first, research-only Laya/Jev comparison interface. Default production use remains Laya-only; Jev remote calls and Active Gate execution are not enabled.

## Quick start

For a plain-language explanation, a worked example, and how to interpret the
latest recorded Search recommendation, see the [Chinese first-use guide](docs/HERMES_FIRST_RUN_ZH.md).

### Requirements

- macOS on Apple Silicon
- Python 3.11–3.13; the hash-locked First-Run dependency set below is for Python 3.12
- Internet access on first model download

From this reviewed source checkout, install into an isolated Python environment:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements/first-run-macos-arm64-py312.lock
python -m pip install --no-deps .
```

Create a named, isolated Hermes profile, check it, and explicitly download the fixed model when needed:

```bash
hermes profile create lsoeval --no-alias --no-skills
local-system-one doctor --profile lsoeval
local-system-one download-model --profile lsoeval
local-system-one install --profile lsoeval
local-system-one start --profile lsoeval
local-system-one shadow --profile lsoeval
local-system-one status --profile lsoeval
```

Verify that the selected profile's registered sessions report effective Shadow before
using the observation. On Hermes 0.23, chat turns run in a Gateway: opening a new
chat does not necessarily reload a plugin the Gateway already loaded in OFF. A
profile-scoped plugin refresh can also reconcile shared MCP connections; use the
[isolated first-use procedure](docs/HERMES_FIRST_RUN_ZH.md) only after confirming
the test Gateway and its connections are not shared with other profiles. The
default source alias is `laya-typed-decisions`; it resolves and verifies this checkpoint revision:

```text
convaiinnovations/laya-typed-decisions
f9ab0b228f0fc0f14d873dbc99038f135c2da1b2
```

The plugin is installed under `~/.hermes/profiles/lsoeval/plugins/local-system-one-hermes`. The Python package lives in the selected virtual environment; Runtime ownership records live under `~/Library/Application Support/Local System One/profiles/lsoeval`. The model is kept in the Hugging Face cache. Failed-start diagnostic logs and a small Runtime lock file can remain in that state directory.

The managed Runtime creates a random bearer credential in the profile's private `access-token` file with user-only file permissions. Hermes, DSH and MCP use that credential for local requests. Other processes running as the same user, and administrators with sufficient access, can also read it and call the API; loopback alone does not restrict access to Hermes. Clients first verify a fresh Runtime identity challenge, then send the token and task on the same connection. A loaded older plugin needs a reload before it can authenticate. Upgrade older HTTP, MCP and DSH clients with the Runtime; the candidate does not fall back to unauthenticated access. Managed startup refuses a conflicting `LOCAL_SYSTEM_ONE_AUTH_TOKEN` instead of silently changing the configured credential.

The service accepts loopback listeners only. It limits request bodies to 1 MiB, active connections to 8, concurrent decision work to 1 and queued decision work to 0. A stalled request receives a timeout; its model work may finish in the background, and new work receives an overload response until that slot is free. Socket reads are limited to 5 seconds, request handling to 10 seconds, and each connection to 15 seconds in total.

The Runtime remains offline with respect to model acquisition. To inspect its local service:

```bash
local-system-one status --profile lsoeval
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
POST /v1/workflows/retry-escalation-gate
GET  /health
GET  /metrics
```

The MCP proxy exposes all five Gates and health. Completion and Retry are advisory only. See [MCP deployment](docs/MCP_DEPLOYMENT.md).

The service binds to loopback by default and does not persist raw task text.

## Optional Apple Neural Engine backend

Install the ANE dependencies:

```bash
python -m pip install '.[ane]'
```

The following historical convenience command downloads L512 from Hugging Face. It does not pin the artifact revision or verify its digest; the reproducible v0.2.0 ANE recipe is still pending:

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

First install is OFF. The first Shadow command displays the destination, data categories and effective profile Gate choices before enabling them. Existing explicit Gate settings are preserved:

```bash
local-system-one install --profile lsoeval
local-system-one shadow --profile lsoeval
local-system-one status --profile lsoeval
```

Shadow mode observes decisions without changing the provider request. The configured sidecar receives bounded task text and recent context; other opt-in Gates can send bounded response or failure context. The default address is loopback. Remote HTTPS requires the separate `--allow-remote` choice, and redirects are refused.

The [official Hermes catalog entry](https://hermes-agent.nousresearch.com/docs/plugins/local-system-one-hermes) still installs plugin `0.6.0` at reviewed commit `1095495019b2dff2b4231ed70ec23a3ea716e2f6`. This candidate contains plugin `0.10.0`; a catalog update is planned for 8.4D.

Rollback is built in:

```bash
local-system-one off --profile lsoeval
local-system-one stop --profile lsoeval --confirm-clients
local-system-one uninstall --profile lsoeval
```

OFF drains registered 0.10 observations before returning. `status` reports those live instances separately; older, unregistered plugin sessions remain UNKNOWN and must be reloaded. Stop requires explicit acknowledgement that all clients sharing that Runtime will be affected. After all profiles have been removed, `python -m pip uninstall local-system-one` removes the shared Python package; model files and Hermes sessions are preserved.

The plugin is designed to **fail open**: if Local System One is unavailable or a recommendation is incomplete, Hermes keeps its original request unchanged.

See [Hermes plugin documentation](integrations/hermes/local-system-one-hermes/README.md) for the full lifecycle and safety constraints.

## DeepSeek Harness integration

The repository includes `local-system-one-dsh`, a native adapter for the official DeepSeek Harness plugin lifecycle. Main source covers **Search, Model Tier, Notification, Completion and Retry / Escalation**; the latter three are Shadow-only. Unified Adapter Contract v1 gives both platforms one versioned semantic contract while preserving platform-specific execution and reversible, fail-open behavior.

Validated DSH targets are deliberately exact:

```text
0.1.7-rc.2  @ 477b4f420553e8a52c2fbccc464d7561b239c443
0.2.1-alpha.1 @ 5badb15009ae1756c3afe0ae0cef1faafc290ccc
```

The adapter supports independent Search, Model Tier, Notification, Completion, and Retry / Escalation observation. Search and Model Tier run at turn start; Notification and Completion observe the completed Agent turn, and Retry can observe an eligible failed tool result. Notification, Completion, and Retry remain Shadow-only. Search Canary retains the audited hard no-Web rules. Model Tier Canary is experimental and disabled by default; when explicitly acknowledged and enabled, only an audited deterministic hard-fast decision on an exact verified provider/model route may copy the first provider request and change `reasoningEffort: high -> low`. Model/probability decisions never receive active authority.

Historical real provider-wire research included the following paths. Phase 8.4C uses local mock providers and does not validate these remote routes:

```text
DeepSeek Harness -> Nova -> DeepSeek V4.1 Flash
DeepSeek Harness -> StepFun Step Plan -> step-5-preview
```

The StepFun route completed native high/low requests and an automatic Local System One high-to-low Canary transition, including tool-loop restoration to high after the first provider call.

The installation bundle remains inert in `off` mode. Connection errors, timeouts, malformed gate responses, unsupported provider/model routes, and any missing Canary authority fail open to native DSH behavior. Turn-scoped Search and Model Tier state is cleared at turn end.

Install the candidate bundle from its local artifact path:

```bash
dsh plugin --profile headless add file:/absolute/path/local-system-one-dsh-0.7.0.tgz
```

The older `dsh-plugin` branch still contains version `0.3.0`. Production Active and Canary use remain unauthorized for this candidate.

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

- The pinned MLX backend clamps the checkpoint's `choice:11+` temperature. Treat
  confidence for Choice requests with 11 or more options as uncalibrated;
  Search uses the separate `noul` primitive.
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

- [Phase 8.4A release baseline and component matrix](docs/PHASE8_4A_RELEASE_BASELINE.md)
- [v0.2.0 product scope](docs/V0_2_PRODUCT_SCOPE.md)
- [Phase 8.3 archive index](docs/PHASE8_3_ARCHIVE_INDEX.md)
- [Phase 8.4B implementation handoff](docs/PHASE8_4B_IMPLEMENTATION_HANDOFF.md)
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
