# SystemOne Benchmark Lab

Apple Silicon 上 System One / typed-decision 模型的可复现实验仓。

当前主线：**Laya ANE Evaluation**。

## Current status

Phase 1–4 are complete on the M4 Mac mini. The research phase is frozen; Phase 5 now turns the validated 421M MLX + L512 ANE hybrid into a usable Local System One service.

Published 322M ANE short-decision baseline:

- compiled MLX FP16: 14.773 ms mean interval
- ANE FP16: 6.408 ms, 2.305× faster than MLX
- ANE W8: 4.598 ms, 3.213× faster than MLX
- gross system energy per decision improves 4.380× (FP16) / 5.820× (W8)
- FP16 and W8 both pass the upstream L96 conversion-fidelity gate

Typed Decisions 421M runtime baseline:

- Core ML CPU+GPU fidelity: 63/63 selected answers, max probability drift 0.00272663, 100/100 repeat stability
- 1-question P50: Core ML 33.715 ms vs MLX 36.055 ms
- 3-question P50: Core ML 102.174 ms vs MLX 84.492 ms
- 10-question P50: Core ML 350.114 ms vs MLX 242.303 ms
- L1024 P50: Core ML 304.921 ms vs MLX 312.202 ms
- ordinary Core ML CPU+NE: 1204.469 ms P50; compute plan prefers CPU, not ANE

Typed Decisions public quality baseline (400 cases / 2,000 decisions):

- Laya Typed Decisions 421M MLX coverage: 100%
- accuracy: 0.7660
- soft accuracy: 0.47064
- KL from gold: 0.11704
- Brier vs soft gold: 0.06147
- ECE (15 bins): 0.21328
- score MAE: 0.24242
- end-to-end case P50 / P95: 513.7 / 2838.6 ms

Frozen reports:

- `results/reports/M4-Laya-ANE-Baseline-v0.1.md`
- `results/reports/M4-Typed-Decisions-421M-Baseline-v0.1.md`
- `results/reports/M4-Typed-Decisions-Quality-Laya-v0.1.md`

Published 322M ANE × Typed Decisions capacity audit:

- public ANE W8 bundle: B1 / L96 / K32
- unmodified benchmark prompt lengths: 127–631 tokens, median 323
- L96 coverage: **0 / 2,000 decisions**
- quality score on this benchmark: **not applicable without changing/truncating inputs**
- hypothetical capacity coverage: L384 79.85%, L512 98.05%, L640 100%

Frozen capacity report:

- `results/reports/M4-Laya-ANE-W8-Typed-Decisions-Capacity-v0.1.md`

421M full-quality backend parity:

- Core ML vs MLX selected decisions: **2,000 / 2,000 identical**
- accuracy: 0.766 on both backends
- max probability delta: 0.0030
- max Score / Noul delta: 0.0039 / 0.0049
- end-to-end case P50: Core ML 887.9 ms vs MLX 513.7 ms
- Core ML / MLX P50 ratio: 1.73×

Frozen parity report:

- `results/reports/M4-Typed-Decisions-421M-CoreML-vs-MLX-Quality-Parity-v0.1.md`

Jev 1.13.0 local independent rerun:

- request alias: `jev-latest`
- concrete model: `jev-1.13.0`
- 400 / 400 cases, 2,000 / 2,000 decisions, zero errors
- accuracy: 0.7370
- soft accuracy: 0.53836
- KL: 1.50336
- Brier: 0.14774
- ECE: 0.04218
- Score MAE: 0.38757
- P50 end-to-end latency from this client: 960.1 ms/case
- 100-case repeat: 9 / 500 selected labels changed (1.8%)

Final Phase 3 reports:

- `results/reports/M4-Jev-1.13.0-Typed-Decisions-v0.1.md`
- `results/reports/Phase3-Jev-Laya-ANE-Final-v1.0.md`
- Jev provenance and public-reference notes: `references/JEV_TYPED_DECISIONS.md`

Phase 4 — 421M long-context ANE engineering:

- full 28-layer L192 / L384 / L512 / L640 bodies: **PASS**
- 10,594 / 10,594 attributed nonconstant operations preferred on ANE at every tested shape
- 421M-tokenizer capacity: L512 **1,966 / 2,000 (98.3%)**; L608/L640 100%
- L512 vs same-subset MLX selected agreement: **99.8%**
- representative real-workload gross system energy / decision: **2.074× improvement vs MLX**
- L640 reaches 100% coverage but loses median single-decision latency to MLX
- practical conclusion: route short/fallback traffic to MLX and suitable medium/long traffic to L512 ANE
- production readiness remains conditional on ANE runtime health gating
- final report: `results/reports/Phase4-421M-ANE-Engineering-Final-v1.0.md`

Next: **Phase 5 — Local System One MVP**.

### Local System One MVP quick start

MLX-only development mode:

~~~bash
PYTHONPATH=. .venv/bin/python -m local_system_one \
  --source models/typed-decisions-source \
  --host 127.0.0.1 \
  --port 8788
~~~

With the validated research L512 ANE package:

~~~bash
PYTHONPATH=. .venv/bin/python -m local_system_one \
  --source models/typed-decisions-source \
  --ane-package experiments/phase4a/typed421-body512-fp16/model.mlpackage
~~~

Endpoints: POST /v1/choice, POST /v1/score, POST /v1/noul, POST /v1/workflows/search-gate, GET /health, GET /metrics.
The service binds to loopback by default and does not log raw request payloads.

First real workflow: **Search Gate v0.1** is functional. It combines hard safety/freshness rules with a conservative System One Noul fallback and has a dependency-free Python client.

- product specification: `docs/LOCAL_SYSTEM_ONE_MVP.md`
- Search Gate design and real smoke findings: `docs/SEARCH_GATE.md`

## 当前目标

1. 将已经验证的 421M MLX + L512 ANE 能力做成常驻 Local System One 服务。
2. 提供 Choice / Score / Noul 三种稳定的 typed-decision API。
3. 用 Router + ANE Health Gate 自动选择 MLX 或 L512 ANE，而不是追求“全 ANE”。
4. 先接入 Search Gate、Model Tier Gate、Notification Gate 三个真实 Agent 工作流。
5. 从真实使用中形成脱敏 Agent Decision Blind Set，再决定是否训练自己的专用模型。
6. MVP 稳定后拆出公开 GitHub 项目，面向其他 Apple Silicon 用户发布。

## 仓库布局

- `references/laya-coreml/`：固定版本的上游 reference（Git submodule）。
- `docs/benchmark-plan.md`：冻结的评测问题、矩阵和口径。
- `scripts/capture_env.py`：采集机器、系统和关键 Python 包版本。
- `benchmarks/`：统一 benchmark 实现。
- `experiments/`：按阶段组织实验。
- `results/raw/`：原始结果。
- `results/processed/`：清洗/聚合结果。
- `results/reports/`：面向人阅读的结果与结论。

## 阶段策略

Phase 1 已完成公开 322M ANE 复现与 M4 能耗基线；Phase 2 已完成 421M
Typed Decisions 的 Core ML / MLX runtime baseline。

Phase 3 已完成统一 decision-quality benchmark，并将 Jev generalist、Laya
specialist、421M backend parity 与公开 ANE 固定形状能力分开报告。

Phase 4 已完成 421M 长上下文 ANE 工程验证，并证明最大固定 shape 并非默认最优解。
研究阶段到此冻结。

Phase 5 转入产品化：构建本地 Decision Service、动态 Router、ANE Health Gate 和 Agent
集成。进一步 ANE 研究只在真实产品需求暴露具体 blocker 时启动。

产品规格见 `docs/LOCAL_SYSTEM_ONE_MVP.md`。

上游基线与固定提交见 `references/UPSTREAM.md`。
