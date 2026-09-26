# Upstream Reference

## laya-coreml

- Repository: https://github.com/mizorewww/laya-coreml
- Pinned commit: `4619e0483f07adf39068532e85b42ec2347edb83`
- Local path: `references/laya-coreml`
- Integration: Git submodule
- Pinned on: 2026-09-23

固定该 revision 的目的：确保公开仓后续更新不会改变我们的历史实验基线。

当前公开 ANE 快速路径聚焦 multilingual 322M、B1/L96；Typed Decisions 421M 已有 Core ML CPU/GPU checkpoint，但不是同一条公开 ANE 快速路径。后续所有结论以本仓固定 revision 的源码和文档为准。

## Typed Decisions 421M Core ML

- Repository: `aac6fef/laya-typed-decisions-coreml`
- Hub revision pinned on 2026-09-23: `28d24fa8d67a3264556b23391ec6c3fd98573056`
- Source checkpoint: `convaiinnovations/laya-typed-decisions@f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`
- Runtime: Core ML CPU + GPU
- Capacity: 1024 total tokens, batch 1, up to 32 option slots
- Role in this project: Phase 2/3 general-purpose 421M baseline before any ANE feasibility work.