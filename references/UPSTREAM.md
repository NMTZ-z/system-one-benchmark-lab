# Upstream Reference

## laya-coreml

- Repository: https://github.com/mizorewww/laya-coreml
- Pinned commit: `4619e0483f07adf39068532e85b42ec2347edb83`
- Historical local checkout: `references/laya-coreml` when present.
- The public source tree does not include this checkout or a Git submodule.
  The optional ANE dependency and build script fetch the pinned revision independently.
- Pinned on: 2026-09-23

固定该 revision 的目的：确保公开仓后续更新不会改变我们的历史实验基线。

Early ANE work focused on multilingual 322M and B1/L96. The later 421M L512
path is documented in the root README. Its public artifact revision and digest
still need to be pinned for the v0.2.0 release; see the
[8.4A baseline](../docs/PHASE8_4A_RELEASE_BASELINE.md).

## Typed Decisions 421M Core ML

- Repository: `aac6fef/laya-typed-decisions-coreml`
- Hub revision pinned on 2026-09-23: `28d24fa8d67a3264556b23391ec6c3fd98573056`
- Source checkpoint: `convaiinnovations/laya-typed-decisions@f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`
- Runtime: Core ML CPU + GPU
- Capacity: 1024 total tokens, batch 1, up to 32 option slots
- Role in this project: Phase 2/3 general-purpose 421M baseline before any ANE feasibility work.
