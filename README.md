# SystemOne Benchmark Lab

Apple Silicon 上 System One / typed-decision 模型的可复现实验仓。

当前主线：**Laya ANE Evaluation**。

## Current status

Phase 1 upstream reproduction is complete on the M4 Mac mini.

Balanced sustained short-decision result:

- compiled MLX FP16: 14.773 ms mean interval
- ANE FP16: 6.408 ms, 2.305× faster than MLX
- ANE W8: 4.598 ms, 3.213× faster than MLX
- FP16 and W8 both pass the upstream L96 conversion-fidelity gate

See `results/reports/M4-Laya-ANE-Baseline-v0.1.md` for the frozen baseline.

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

## 第一阶段

先完成公开实现复现，不改模型结构，不下载不必要的大型权重，不提前做 421M ANE 重写。

上游基线与固定提交见 `references/UPSTREAM.md`。
