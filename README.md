# SystemOne Benchmark Lab

Apple Silicon 上 System One / typed-decision 模型的可复现实验仓。

当前主线：**Laya ANE Evaluation**。

## Current status

Phase 1, Phase 2, and the Phase 3A Laya quality baseline are complete on the M4 Mac mini.

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

Next: Phase 3B Jev 1.13.0 zero-shot measurement. The runner is ready; the current execution environment still needs a TypeSafe API key exposed via `TYPESAFE_API_KEY`.

## 当前目标

1. 在 M4 Mac mini 上复现公开 `laya-coreml` 的 ANE 结果。
2. 用统一边界比较 MLX、Core ML CPU/GPU 与 Core ML ANE。
3. 分开衡量转换保真度、真实任务质量、延迟、能耗、内存与启动成本。
4. 评估 421M Typed Decisions checkpoint 是否值得继续做 ANE 工程化。
5. 后续把 Jev 纳入同一评测框架，但不混淆“模型质量”和“运行后端性能”。

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

Phase 3 开始统一 decision-quality benchmark。模型质量与运行后端性能必须分开
报告；在质量评测和结构可行性分析完成前，不提前承诺 421M ANE 重写。

上游基线与固定提交见 `references/UPSTREAM.md`。
