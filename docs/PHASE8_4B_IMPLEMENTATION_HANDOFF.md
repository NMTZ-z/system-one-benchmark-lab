# Phase 8.4B — Hermes First-Run MVP handoff

Start from the reviewed **8.4A research-integration baseline**, not the older
#14 head. While the integration PR is Draft, use its exact reviewed head in a
separate worktree. If it has been merged, verify the new main contains that
head and use the current reviewed main commit. The integration PR records its
head SHA externally because a commit cannot embed its own SHA. Preserve all
existing Gates and the existing Agent's configuration and behavior.

## Fixed scope and code entry points

- CLI and service: `local_system_one/{cli,service,health}.py`,
  `runtime/{sources,mlx}.py` and existing lifecycle scripts.
- Hermes plugin and profile lifecycle:
  `integrations/hermes/local-system-one-hermes/{plugin.yaml,__init__.py}`,
  `scripts/{hermes_system_one_common,install_hermes_system_one_plugin,set_hermes_system_one_mode,hermes_system_one_status,uninstall_hermes_system_one_plugin}.sh`.
- Existing tests: `tests/test_hermes_system_one_plugin.py`,
  `tests/test_hermes_system_one_scripts.py`, `tests/test_runtime_sources.py`,
  `tests/test_adapter_contract.py` and relevant Gate/service tests.
- The current optional Kanban task resolver imports private Hermes modules.
  The admission validator warns these can drift. Test its fail-open fallback
  and pursue a supported seam if required for catalog compatibility; preserve
  existing task resolution unless a deliberate, tested replacement is made.
- Keep the existing project structure. Prefer a small extension of these entry
  points to a new framework or daemon. Complete MCP and DSH distribution in
  8.4C. Historical H4 executors are retained in the repository for research;
  do not wire them into the Runtime or execute them.

## User-operation contract

Command spelling can follow the existing CLI; every operation must be available
and explained. Return actionable errors without printing secrets or raw tasks.

| Operation | Required effect |
|---|---|
| `doctor` | Without changing the selected profile or sending task content, inspect Apple Silicon/macOS, supported Python, plugin/profile prerequisites, loopback destination, pinned model availability, disk/permissions and Runtime health. Explain whether an explicit model download or installation is needed. |
| `start` | Start a user-owned local Runtime with pinned Laya/MLX and loopback binding; report owned process and health. Detect an existing listener without killing or claiming an unrelated process. Persistent service installation requires opt-in. |
| `shadow` | Target the named profile. First use selects Search only; other Gates require explicit per-Gate opt-in. Show destination, enabled Gates and data categories before enabling. Non-loopback use requires explicit informed consent and redirect protection. Shadow preserves the native request, tools and Agent control flow. |
| `status` | Show selected profile, installed versions, requested and **effective** mode, Gate switches, endpoint, health, owned process state, last bounded decision/error summary and any required reload. Never include raw task/response text or credentials. |
| `off` | Revoke observation. After the command reports effective OFF, new Agent events generate zero new sidecar requests, including in long-lived plugin instances. Already in-flight work must be accounted for: drain/cancel safely or delay acknowledgement until no later sends are possible. If reload/restart is necessary, say so and do not claim OFF is effective prematurely. |
| `stop` | Stop only a Runtime process owned by this installation, after identity verification; leave other services and profiles alone. Repeated stop is safe. |
| `uninstall` | Disable the selected plugin, remove only explicitly owned plugin/runtime artifacts and state, and preserve other profiles, sessions, credentials, models and user configuration. Repeat safely. Explain any user-selected data removal. |

If the Runtime is unavailable, times out or gives invalid data, Hermes follows
its original path and records a bounded failure summary. An upgrade must
validate a staged copy and restore the previous usable installation and
configuration on failure. Do not silently overwrite a nonmatching plugin.

## Acceptance checks

1. Isolated clean install with no old experiment directory or private evidence;
   verify model revision, dependency provenance and usable doctor diagnostics.
2. OFF at install; a first Shadow transition observes Search only. Count calls
   per Gate, prove no changes to provider request/tools/Agent outcome, and
   exercise explicit later opt-in for each other Gate.
3. Unavailable Runtime, timeout, malformed response, and process start failure
   all preserve native behavior and produce safe status. Check requested vs
   effective state across long-lived process/reload boundaries.
4. OFF acknowledgement yields zero subsequent observation requests, including
   queued/background observer races. Test repeated OFF, stop and uninstall;
   verify unrelated processes, profiles, configs, sessions and data survive.
5. Upgrade failure restores prior plugin bytes, activation and settings; test
   interruption and nonmatching existing directory. Use only isolated
   profiles, owned processes and local mocks unless separately authorized.
6. Run relevant Python/Hermes tests, contract checks, release sanitizer and
   source/license checks on the exact clean candidate. Separately report native
   Hermes validation, clean installation and actual model loading as performed,
   skipped or blocked; mock tests are not real user-value evidence.
7. Freeze the tested commit and artifact digests in the manifest and provide
   `v0.2.0-rc.1` only when all 8.4B acceptance checks pass.

## Copyable next-window prompt

```text
开始 Local System One Phase 8.4B — Hermes First-Run MVP。

先核对 GitHub main 和 8.4A 集成 PR 的精确 head SHA：如仍为 Draft，
基于该 head 建立独立 worktree；如已合并，核实 main 包含该 head 后以
当前审阅过的 main 建立 worktree。旧的 #14 head 不含本次研究集成。以
docs/V0_2_PRODUCT_SCOPE.md、docs/PHASE8_4A_RELEASE_BASELINE.md、
docs/PHASE8_4B_IMPLEMENTATION_HANDOFF.md 和 release/v0.2.0-manifest.json
为已冻结契约。以 GitHub 实际状态为准；正式合并需主人确认。

目标：让用户在指定的独立 Hermes Profile 中完成 doctor、start、shadow、
status、off、stop、uninstall。默认本地 Laya/MLX 和回环地址，安装后 OFF，
首次 Shadow 只观察 Search，其他 Gate 必须逐项选择。明确 Sidecar 目的地址
与数据流；只有用户明确同意才能使用非本地地址。Shadow 不改变原生 Agent
请求和执行，Runtime 不可用时保留原生行为。OFF 在实际生效并处理完在途工作后
才可确认，之后不得新增观察请求。状态展示有效模式、Gate、健康和安全的决策摘要。

沿用现有 CLI、Runtime、Hermes 插件、Profile 脚本及测试；补齐安装预检、
固定模型检查、独立 Profile 安装、可回退升级、仅停止自有 Runtime、重复卸载和
不损坏其他配置或数据。用独立环境和本地模拟执行干净安装、全生命周期、
故障回退、OFF 竞态、升级失败与数据保留测试，并核对契约、来源、许可证和
公开发布扫描。将实际运行、跳过或受阻的验证分别写清。合格后绑定精确提交、
工件与摘要，准备 v0.2.0-rc.1 和 Draft PR。

保留五个现有 Gate；不新增 Gate，不启动 H4E，不引入自动重试、自动停止、
付费模型升级、热切换或 Dashboard，不改生产 Hermes 配置，不安装常驻服务，
不部署 MCP，不调用真实付费 Provider，不擅自合并任何 PR。HTTP/MCP 和 DSH 的
后续发行工作留给 8.4C；Luna 只可在 8.4C 单独研究。生产 Active、正式发布
及真实 Owner Shadow 使用需要相应阶段的明确授权。
```
