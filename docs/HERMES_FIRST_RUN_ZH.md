# Local System One：第一次使用说明

本说明对应 v0.2.0 的本地发行候选。正式发行之前，请以候选的验收结论和发行清单为准。

## 它会做什么

System One 在电脑上运行一个小模型，给 Agent 的部分工作判断提供建议。第一次体验只观察
“当前任务是否需要公开网络搜索”。你原来的 Agent 和主模型继续负责回答和使用工具。

例如，你请 Agent 根据已经提供的材料想 5 个选题。System One 可能建议 `no_search`，
意思是“它判断这项任务不需要搜索公开网页”。换一个需要最新公开资料的问题，它可能
建议 `search`。这两种结果都有可能出错，需要结合任务判断。

第一次体验使用 Shadow（观察模式）：System One 记录建议，Agent 仍按自己的流程工作。
它不会因为接入就提高创意质量，也不能据此判断是否节省时间、Token 或费用。

## 开始之前

- 准备 Apple Silicon Mac、Hermes、Python 3.12 和独立的测试 Profile。测试过的版本
  及其他要求见 [README 的 Quick start](../README.md#quick-start)。
- 本地模型第一次下载和安装依赖可能需要联网；先确认下载内容和来源。已有经过校验的
  模型缓存可以复用。主模型是否联网取决于你原有的 Provider 设置。
- 确认测试 Profile、原有任务和服务的情况。多个 Profile 可能共用 Hermes 服务、工具
  连接或电脑资源；开启、关闭或卸载前都要检查影响范围。
- 默认本地服务接收有长度限制的当前任务与近期上下文。首次观察作用于选定 Profile，
  同时进行的其他会话也可能被观察。请先确认内容范围与时段。Hermes 本身如何保存对话，
  取决于 Hermes 的设置。

## 安装和开启

以下命令使用新建的 `lsoeval` 测试 Profile。先在已审阅的源码目录按照
[Quick start](../README.md#quick-start) 创建 Python 环境并安装依赖，然后执行：

```bash
hermes profile create lsoeval --no-alias --no-skills
local-system-one doctor --profile lsoeval
```

如果 `doctor` 提示缺少模型，确认后使用 `local-system-one download-model --profile lsoeval`
下载固定模型。模型已经就绪后，继续：

```bash
local-system-one install --profile lsoeval
local-system-one start --profile lsoeval
local-system-one shadow --profile lsoeval
local-system-one status --profile lsoeval
```

安装后的默认模式是 OFF；`shadow` 才会开启观察。开启命令会先
显示服务地址、数据类别和选定的观察项。已存在的显式 Gate 设置会保留；全新默认配置的
首次观察只启用 Search。

Hermes 0.23 的聊天由 Gateway 承载。如果它已经以 OFF 加载插件，单独新建聊天或运行
`hermes -p lsoeval chat` 不保证插件重新加载。先确认 `status` 显示已登记会话的实际模式
为 `shadow`；只有 `CONFIGURED mode: shadow` 时还不能认定观察已经生效。

如果已经确认 **测试 Gateway 及其工具连接由 `lsoeval` 独占**，且插件管理不会变更
其他 Profile 的共用依赖，可以按以下顺序关闭旧观察、刷新目标插件并重新开启：
如果测试 Gateway 尚未运行，先打开空的测试会话，暂不输入任务；之后在另一个终端执行：

```bash
local-system-one off --profile lsoeval
hermes -p lsoeval plugins disable local-system-one-hermes
local-system-one shadow --profile lsoeval
hermes -p lsoeval plugins enable local-system-one-hermes --no-allow-tool-override
local-system-one status --profile lsoeval
```

如果刷新后状态仍为 `UNKNOWN` 或 `PENDING_RELOAD`，请停止并核实目标 Gateway 是否
已重新加载插件。只有确认实际模式为 `shadow`，才能把后续判断当作有效观察。
插件刷新会让 Hermes 核对工具连接；
如果 Gateway 或工具连接可能与其他 Profile 共用，或者无法确认归属，请先停止并核实，
不要重启共享 Gateway。旧会话仍可能使用旧设置，需要单独结束或重载；同一 Profile 的
多个会话也可能同时写入记录。

确认生效后，可以使用 `hermes -p lsoeval chat`，让它完成一项你允许的任务。

## 看懂结果

在同一个 Python 环境运行：

```bash
local-system-one status --profile lsoeval
```

输出中的几个关键项目：

| 项目 | 含义 |
|---|---|
| `CONFIGURED mode` | 配置中请求的模式，例如 `off` 或 `shadow`。 |
| `EFFECTIVE mode of registered v0.10 sessions` | 已登记会话实际报告的模式；`UNKNOWN` 或 `PENDING_RELOAD` 表示还不能确认。 |
| `Last Search recommendation` | 最近一次保存的搜索建议：`search` 表示建议搜索，`no_search` 表示建议不搜索，`UNKNOWN` 表示没有可确认的建议。 |
| `recorded UTC` | 上述记录的世界标准时间；`UNKNOWN` 表示没有可用时间。北京时间为 UTC 时间加 8 小时，跨日时日期也要调整。 |
| `Last Search decision source` | `model` 表示模型给出的判断，`rule` 表示固定规则。 |
| `latency ms` / `failure` | 观察耗时（毫秒）及可安全显示的失败类别。 |

“最近一次”可能来自之前的任务，甚至来自同一 Profile 的其他会话。请结合记录时间和
自己的操作判断；这条状态不能证明记录一定对应当前对话。状态展示来源和结果，不提供
模型的完整推理过程。Shadow 下该建议不会改写主模型请求；看到建议不代表 Agent 已经
按建议搜索或停止搜索。

## 关闭、停止和卸载

结束体验后，先关闭观察并查看状态：

```bash
local-system-one off --profile lsoeval
local-system-one status --profile lsoeval
```

`CONFIGURED mode: off` 说明配置已请求关闭。已登记会话显示 `EFFECTIVE_OFF` 才说明这些
会话已确认关闭；旧的未登记会话可能仍为 `UNKNOWN`，需结束或重载后单独核实。

确认本次启动的 Runtime 没有其他使用者后，停止服务；如需移除插件，再执行卸载：

```bash
local-system-one stop --profile lsoeval --confirm-clients
local-system-one uninstall --profile lsoeval
```

`--confirm-clients` 表示你确认停止会影响所有共用该 Runtime 的客户端。卸载会通过 Hermes
处理插件配置和依赖；确认不会影响其他成员后再执行。共享 Python 包需要在所有 Profile
移除后另行卸载；模型缓存和 Hermes 会话数据会保留。遇到状态不明、其他成员异常或
服务归属不清时，停止操作并保留现场。
