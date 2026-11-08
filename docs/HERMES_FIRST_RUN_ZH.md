# Local System One v0.2.0：从安装到第一次 Shadow

> **适用版本：** [GitHub 正式版 v0.2.0](https://github.com/NMTZ-z/system-one-benchmark-lab/releases/tag/v0.2.0)，Hermes 插件 0.10.0。本文同时适用于**已有 Hermes Profile** 和新建测试 Profile，无须强制新建 Profile。

## 先弄清楚三个问题

**安装插件后会自动工作吗？** 不会。Hermes 插件安装后默认 **OFF**，本地 Runtime 也需要单独安装和启动。可以把 Runtime 理解为决策服务，把 Hermes 插件理解为接线器：只有两边准备好、你主动开启 Shadow，才会开始观察。

| 模式 | System One 的行为 | Hermes 会受到什么影响 |
|---|---|---|
| **OFF（默认）** | 不调用本地决策服务 | Hermes 按原样工作 |
| **Shadow（建议先用）** | 用本地 Laya 判断、记录 Search 建议 | **不改写**主模型请求和工具 |
| **Canary** | 允许少量经过审计的规则更改请求 | 可能改变行为；**不属于本版的生产使用授权** |

全新配置首次进入 Shadow 时，只启用 **Search Gate**。Model Tier、Notification、Completion、Retry 和 Completion Loop Probe 均默认关闭。以后可以逐项选择；已有 Profile 的明确设置会保留。

**Shadow 看什么？** 例如你让 Agent 翻译已有文字，本地模型可能建议 `no_search`；询问最新政策，它可能建议 `search`。Hermes 仍自行决定是否搜索。Shadow 不会直接节省主模型 Token，运行本地模型也会占用少量电脑资源。

## 第一步：准备 Runtime（首次安装一次）

需要 Apple Silicon Mac、Hermes、Python 3.12（这是已验证的安装路径）及可用磁盘空间。已验证过的模型缓存可复用；**只有缺少模型时才手动下载**。普通 Hermes 任务使用的主模型和费用由你原有 Provider 决定。

从固定发行 Tag 获取源码和锁定依赖，安装到独立 Python 环境，避免覆盖 Hermes 自己的 Python：

```bash
git clone --branch v0.2.0 --depth 1 https://github.com/NMTZ-z/system-one-benchmark-lab.git
cd system-one-benchmark-lab
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements/first-run-macos-arm64-py312.lock
python -m pip install --no-deps .
```

以后使用 `local-system-one` 命令时，先进入这个环境并运行 `. .venv/bin/activate`。如果系统提示 `command not found`，先检查这一步。

## 第二步：选定 Hermes Profile

**已有 Hermes 用户：** 用自己现有的 Profile 名称替换下面的 `lsoeval`。无需创建新 Profile。如果该 Profile 已安装正式插件 0.10.0，也无需重复安装。

**想新建测试 Profile：** 可选择执行下面这条命令（已有 Profile 跳过）：

```bash
hermes profile create lsoeval --no-alias --no-skills
```

以下用 `lsoeval` 举例，后续所有命令都要使用**同一个 Profile 名称**。

先检查环境：

```bash
local-system-one doctor --profile lsoeval
```

`NEEDS_SETUP` 说明还缺模型、插件或依赖；按提示补齐即可。`BLOCKED` 说明有必须解决的环境问题，例如端口冲突。预检本身不会下载模型或开启服务。

**仅在模型缺失且你同意联网下载时**运行：

```bash
local-system-one download-model --profile lsoeval
```

**仅在该 Profile 尚未安装正式插件时**运行：

```bash
local-system-one install --profile lsoeval
```

注意：Hermes 官方 Catalog 的条目在本文更新时仍指向旧版 `0.6.0`。如果你想使用 `0.10.0`，先核对 [上游更新 PR](https://github.com/NousResearch/hermes-agent/pull/150745) 是否已合并，或直接采用 v0.2.0 的固定发行源码。安装完成后应核对 `status` 中的插件版本。

## 第三步：启动 Runtime，再主动开启 Shadow

```bash
local-system-one start --profile lsoeval
local-system-one shadow --profile lsoeval
local-system-one status --profile lsoeval
```

`start` 会启动只监听 `127.0.0.1:8787` 的本地 Runtime，并验证真正的 Laya／MLX 推理。首次 Shadow 会显示请求目的地址、可能传递的数据类别和已启用的 Gate。默认服务需使用专用本地凭据；任务正文不会被默认写入决策记录。

**成功要看两层状态：**

- `CONFIGURED mode: shadow`：配置已经要求开启。
- `EFFECTIVE mode of registered v0.10 sessions: shadow` 与 `EFFECTIVE search: true`：当前已登记的插件会话确实在观察。

如果只显示 `PENDING_RELOAD` 或 `UNKNOWN`，目前还不能确认真实观察已经生效。请看下一节。

## Shadow 已配置但没生效怎么办

Hermes 0.23 的聊天可能由**常驻 Gateway** 承载。只打开新聊天，未必会重新加载旧的 OFF 插件。你需要让目标 Profile 的插件重新加载，再查看 `status`。

**如果 Gateway 或 MCP 连接被多个 Profile 共用：** 不要为了一个插件直接重启整个 Gateway，也不要随意对它执行禁用、启用。应由管理者先确认连接归属，再进行目标 Profile 的定向热刷新。刷新后检查所有其他 Profile 仍正常。这里的刷新可能重新协调 MCP 连接。

**仅当确认测试 Gateway 和它的工具连接都由该 Profile 独占时**，可以按已验证的插件管理流程：

```bash
local-system-one off --profile lsoeval
hermes -p lsoeval plugins disable local-system-one-hermes
local-system-one shadow --profile lsoeval
hermes -p lsoeval plugins enable local-system-one-hermes --no-allow-tool-override
local-system-one status --profile lsoeval
```

如果仍然显示 `PENDING_RELOAD` 或 `UNKNOWN`，停止刷新操作，确认实际插件加载状态；**不要因为配置变成 Shadow 就声称启用成功**。旧版未登记会话也可能保持 `UNKNOWN`，需要结束或重载后单独核对。

## 第四步：做一次正常任务，看看判断

在选定 Profile 中运行自己的常规 Hermes 任务，例如：

> 请用一句话解释压缩空气储能膨胀机的作用。

然后查看：

```bash
local-system-one status --profile lsoeval
```

| 看到的字段 | 人话解释 |
|---|---|
| `Last Search recommendation: no_search` | System One 建议当前任务无须公开搜索 |
| `Last Search recommendation: search` | System One 建议需要公开搜索 |
| `Last Search decision source: rule / model` | 建议来自固定规则或本地 Laya 模型 |
| `latency ms` | 这次观察的耗时 |
| `recorded UTC` | 记录时间（北京时间为 UTC+8） |
| `failure` | 最近一次观察是否失败及安全失败类别 |

这些字段只展示**最近一次记录**，可能来自前一个任务，或同一 Profile 的其他会话；要结合时间判断。`no_search` 是建议，Shadow 并不会阻止 Hermes 搜索。

## 关闭、停止、卸载

**只想暂停观察：**

```bash
local-system-one off --profile lsoeval
local-system-one status --profile lsoeval
```

`CONFIGURED mode: off` 只表示配置已写入；对于已登记的 0.10 会话，还应看到 `EFFECTIVE_OFF`。旧版未登记会话要通过重载或结束进一步核实。

**想同时停止本地 Runtime：** 先确认没有其他客户端在使用，再执行：

```bash
local-system-one stop --profile lsoeval --confirm-clients
```

**需要移除插件：**

```bash
local-system-one uninstall --profile lsoeval
```

卸载保留模型缓存、原有 Hermes 会话和无关 Profile；共享 Python 环境需要另行管理。遇到归属不明的服务、共享 Gateway 或异常状态，应停止操作并核实，避免影响其他 Agent。

## 常见疑问

- **只安装了 Hermes 插件却没有记录？** 查看 Runtime 是否已安装并 `HEALTHY`、当前模式是否为 `EFFECTIVE shadow`。
- **出现 401／认证错误？** 核对 Runtime 与插件是否都是正式版，旧插件可能不支持新认证，需要升级并重新加载。不要关闭认证来绕过问题。
- **服务不通会卡住 Hermes 吗？** 插件按 fail-open 设计，遇到不可用、超时或错误时让 Hermes 继续原生任务。
- **可以一开始打开所有 Gate 吗？** 首次建议只观察 Search。Completion、Retry 的建议仍然不会自动终止或重试任务；Canary 不属于本版的生产使用授权。

完整能力和工程限制见 [项目 README](../README.md)；正式安装工件见 [GitHub Release v0.2.0](https://github.com/NMTZ-z/system-one-benchmark-lab/releases/tag/v0.2.0)。
