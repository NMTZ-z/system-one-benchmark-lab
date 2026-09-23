# Laya ANE Evaluation Plan v1.0

日期：2026-09-23

## 1. 研究问题

### Q1：公开 ANE 实现能否在 M4 Mac mini 上稳定复现？

先复现上游 322M multilingual ANE L96 FP16 / W8 的功能与性能结果。

### Q2：ANE 的收益到底来自哪里？

在相同输入与相同计时边界下比较：

- compiled MLX FP16
- Core ML CPU + GPU
- Core ML CPU + ANE FP16
- Core ML CPU + ANE W8

重点区分：
- 端到端单次 decision 延迟；
- 纯模型执行与输入/输出边界；
- 吞吐；
- 整机功耗和单 decision 能耗。

### Q3：转换后是否仍然“做同一件事”？

把 conversion fidelity 与 task quality 分开：

- conversion fidelity：同一输入下 selected answer 一致率、概率漂移、重复调用稳定性；
- task quality：在独立 benchmark 上比较准确率、概率质量、稳定性。

公开仓的 fixture 只能证明转换保真度，不能直接替代任务准确率评测。

### Q4：421M Typed Decisions 是否值得做 ANE？

只有在以下条件满足后才进入工程化：

1. 322M ANE 路线在本机可稳定复现；
2. M4 上的收益具有实际意义；
3. 421M CPU/GPU baseline 已冻结；
4. 能明确识别 421M → ANE 的主要结构/shape 障碍。

## 2. 第一阶段测试矩阵

| Model | Backend | Context | Purpose |
|---|---|---:|---|
| Multilingual 322M | MLX FP16 | matched short input | performance reference |
| Multilingual 322M | Core ML CPU+GPU | matched short input | conversion/runtime reference |
| Multilingual 322M | Core ML CPU+ANE FP16 | L96 | ANE reproduction |
| Multilingual 322M | Core ML CPU+ANE W8 | L96 | quantized ANE reproduction |
| Typed Decisions 421M | Core ML CPU+GPU | up to L1024 | 421M baseline |

第二阶段再加入 Jev 与 421M ANE feasibility。

## 3. 指标

### 3.1 正确性与保真度

- selected-answer agreement
- calibrated probability absolute drift
- maximum probability drift
- repeated-call determinism/stability
- failure / capacity error rate

### 3.2 延迟

所有结果都必须注明计时边界。

- model load time
- first inference latency
- warm P50 / P95 / P99
- mean / standard deviation
- decisions per second

注意：Laya 不进行自回归 token 生成，因此不用“TTFT/首 token 延迟”表述。

### 3.3 能耗

优先记录：

- mean system power during stable measurement window
- energy per decision
- background/load-control notes
- sampling method and rejected samples

能耗与延迟必须使用相同 workload，并避免把速度收益重复乘入能效收益。

### 3.4 资源

- model/package size
- peak RSS
- steady RSS
- cold initialization time

## 4. 实验纪律

1. 固定模型 revision、源码 commit、macOS、Python 和关键包版本。
2. 每次实验保存原始 JSON/CSV，不只保存最终表格。
3. cold 与 warm 分开测。
4. 不把 L96 短输入结果外推为 L1024 长上下文结果。
5. 不把 conversion fixture 的一致率描述为通用任务准确率。
6. 不把单次 decision API 延迟描述为完整应用/游戏帧耗时。
7. 每项性能结论都标明机器型号、系统版本和 workload。
8. 421M ANE 开发必须由评测结果触发，而不是为了“已经立项所以必须做”。

## 5. 阶段门

### Phase 0 — Baseline Freeze
- 固定上游 commit
- 采集环境
- 确认模型与 benchmark 入口

### Phase 1 — Upstream Reproduction
- 复现官方短 decision workload
- 验证 FP16 与 W8
- 保存 M4 原始数据

### Phase 2 — Unified Runtime Comparison
- 统一 MLX / Core ML GPU / ANE 的输入和计时边界
- 输出 latency / energy / memory 对比

### Phase 3 — Decision Benchmark
- 接入独立任务集
- 比较模型质量、概率质量和稳定性
- 后续接入 Jev

### Phase 4 — 421M ANE Feasibility
- 只有通过前述阶段门后才开始
- 优先做结构与 shape 可行性，不先承诺完整移植

## 6. 第一份交付

`M4-Laya-ANE-Baseline-v0.1`：

- 环境快照
- 上游 commit
- 模型 revision
- reproduction 命令
- correctness / fidelity
- latency
- energy（若测量链路可用）
- 与上游 M3 Max 数字的“不同硬件条件下观察”，不做不严谨的直接优劣归因
