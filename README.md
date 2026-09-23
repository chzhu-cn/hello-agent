# Hello Agent

一个逐步学习 AI Agent 开发的 Python 实践项目：先用模型 SDK 手写执行流程，理解消息、工具、计划、检查和角色交接，再用框架实现相同案例进行对照。

技术路线：**SDK 手写 → SDK 扩展实验 → Pydantic AI → LangChain → LangGraph**。当前使用 OpenAI Python SDK 调用 OpenAI 兼容的 Chat Completions 接口，模型与服务地址由配置决定。

## 当前进度

截至 2026-09-22，SDK 的 P0–P4 已实现并有验证记录；E01–E03 已有分步实验，当前推进 E04 结构化输出最小对照。

| 学习项 | 当前能力 | 学习记录 |
| --- | --- | --- |
| P0 基础调用 | 单次文本请求；一次 add 工具调用与结果回传 | [P0](docs/patterns/p00_basics.md) |
| P1 ReAct 风格循环 | 连续工具调用、消息历史、参数校验和请求步数上限 | [P1](docs/patterns/p01_react.md) |
| P2 Plan-and-Execute | 生成依赖计划、执行前有限修正、Python 执行与模型汇总 | [P2](docs/patterns/p02_plan_execute.md) |
| P3 Reflection / Critique | 固定计算记录、初稿、结构化检查、有限修改与复查 | [P3](docs/patterns/p03_reflection.md) |
| P4 多 Agent 协作 | 协调者一次委派，计算者独立工具循环，返回后汇总 | [P4](docs/patterns/p04_multi_agent.md) |
| E01-A 进程内会话 | 连续文本对话、会话隔离、失败轮不写入历史 | [E01-A](docs/e01_memory.md) |

P 表示 Pattern（执行模式），E 表示 Extension（扩展能力）；`P1` 与目录中的 `p01` 是同一编号，`E01-A` 是 E01 的第一个小实验。这是本项目的学习编号。

E02 已实现全量、窗口、摘要及本地估算预算和工具历史整轮裁剪，尚非精确模型计数。E03-A 已实现六题最小评估，E04 已实现结构化输出最小对照；完整工具轨迹评估、E05–E13 及三个框架阶段尚未实现，具体范围见 [SDK 扩展学习计划](docs/sdk-learning-plan.md)。实际完成状态以 [任务清单](docs/tasks.md) 为准。

## 安装与配置

准备 Python 3.14 和 uv，以下命令均在项目根目录执行。

```sh
uv sync
```

如果没有 `.env`，复制 `.env.example` 为 `.env`；已有配置直接编辑。填写服务提供的模型名称、密钥和 API 基础地址。基础地址不要包含 `/chat/completions`，示例域名需要替换。

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `LLM_MODEL` | 必填 | 模型名称 |
| `LLM_API_KEY` | 必填 | 服务密钥，使用 SecretStr 脱敏 |
| `LLM_BASE_URL` | 运行入口要求配置 | OpenAI 兼容 API 基础地址 |
| `LLM_TIMEOUT` | `30` | 单次请求超时，单位秒，必须大于 0 |
| `AGENT_MAX_STEPS` | `5` | P1 每次任务最大模型请求次数，1–100 |
| `PLAN_MAX_STEPS` | `5` | P2 最大计划步骤数，1–100 |
| `PLAN_MAX_REPAIRS` | `1` | P2 无效计划最大修正次数，0–2 |
| `REFLECTION_MAX_REVISIONS` | `1` | P3 最大答案修改次数，0–2；每次修改后复查 |
| `COOP_WORKER_MAX_STEPS` | `5` | P4 计算者最大模型请求次数，1–100 |

默认值来自配置模型，实际运行受 `.env` 或环境变量覆盖。配置统一在 `config/settings.py` 导入时初始化；配置无效由 Pydantic 直接报告。日志使用 logly，SDK 自动重试关闭。工具调用示例要求所选模型服务支持工具调用；P2/P3/P4 还包含需要本地校验的 JSON 输出。

## 运行示例

### P0：单次模型调用与工具调用

```sh
uv run hello-agent
uv run hello-agent "用一句话解释什么是工具调用"
uv run python -m hello_agent.sdk.p00_basics.tool_call
```

`hello-agent` 仍指向 P0 单次文本调用，发送输入后输出回复并退出。工具示例请求计算 `127 + 358`，最多执行一个工具、发送两次模型请求，预期结果为 `485`。

### P1：连续工具调用

```sh
uv run python -m hello_agent.sdk.p01_react.agent
```

默认先计算 `127 + 358`，收到工具结果后再加 `96`，预期得到 `581`。支持在命令末尾传入自定义任务字符串。程序维护一次任务内部的消息历史，模型给出最终回答或达到请求上限时停止。

### P2：先规划再执行

```sh
uv run python -m hello_agent.sdk.p02_plan_execute.agent
```

默认执行相同的两步加法，也支持自定义任务字符串。模型生成包含步骤依赖的计划，Python 校验并执行，模型再汇总结果。无效计划只能在执行前有限修正，执行失败不自动重跑整个计划。

### P3：检查与有限修改

```sh
uv run python -m hello_agent.sdk.p03_reflection.agent
```

Python 先完成固定两步加法，再让模型生成初稿、检查并按额度修改。修改不会重跑工具。检查通过不保证事实正确：已有错误工具依据实验出现修正失败和误判通过，详情见 P3 学习记录。

### P4：一次委派与返回

```sh
uv run python -m hello_agent.sdk.p04_multi_agent.agent
```

协调者将固定计算任务委派给计算者，计算者通过 add 完成计算并返回记录，协调者汇总。两个角色使用独立消息历史和不同工具权限，可以共用同一模型。日志展示角色交接、请求次数、工具结果及停止状态。

### E01-A：进程内多轮会话

```sh
# 固定演示：告知偏好、追问、新建会话再次询问
uv run python -m hello_agent.sdk.e01_memory.agent

# 交互体验
uv run python -m hello_agent.sdk.e01_memory.agent --interactive
```

先输入“我最喜欢青绿色”，再问“我最喜欢什么颜色？”。输入 `/new` 新建空会话，`/exit` 退出。每轮将当前会话全部历史再次发送给模型，成功后保存用户输入和助手回复；失败轮不写入历史，也不自动重试。

本步为纯文本会话，没有工具调用。不提供会话名称时，历史仅保存在当前进程内，退出后丢失；尚无摘要或输入预算控制。

### E01-B：保存与恢复会话

```sh
uv run python -m hello_agent.sdk.e01_memory.agent --interactive --session colors
```

退出后用相同命令恢复历史。默认保存到 `.local/sessions`，可用 `.env` 的 `MEMORY_DIRECTORY` 修改。每轮成功后保存；`/new` 生成并显示新会话名称，保留旧文件。文件损坏时明确退出，不覆盖历史。仅支持单进程依次写入同一会话，详见 [E01 学习记录](docs/e01_memory.md)。

### E01-C：独立偏好档案

```sh
uv run python -m hello_agent.sdk.e01_memory.preferences --profile demo --set 颜色 青绿色
uv run python -m hello_agent.sdk.e01_memory.preferences --profile demo --ask "我最喜欢什么颜色？"
uv run python -m hello_agent.sdk.e01_memory.preferences --profile demo --delete 颜色
```

再次设置同名键即可更新；`--show` 查看当前档案。偏好保存在 `MEMORY_DIRECTORY` 下的独立文件。提问只发送当前偏好和问题，不携带旧聊天；删除偏好不会擦除旧会话中的文字。完整实验见 [E01 学习记录](docs/e01_memory.md)。

### E02-A：全量历史与最近几轮

```sh
uv run python -m hello_agent.sdk.e02_context.agent --preview
uv run python -m hello_agent.sdk.e02_context.agent
```

第一条仅展示消息，第二条发起两次模型请求。窗口默认保留最近两轮，可在 `.env` 设置 `CONTEXT_RECENT_TURNS`。原始历史不会被裁剪覆盖；详见 [E02 学习记录](docs/e02_context.md)。

## 验证与已观察到的结果

E05-A 本地 MCP：`uv run python -m hello_agent.sdk.e05_mcp.client`。自动启动服务子进程，发现 add 并调用得到 485；无需模型或 API 密钥。详见 [E05 学习记录](docs/e05_mcp.md)。

E04 结构化输出：`uv run python -m hello_agent.sdk.e04_structured.agent`。同一颜色提取任务分别使用提示 JSON 与 json_schema 参数，两种结果都经 Pydantic 和独立事实校验。详见 [E04 学习记录](docs/e04_structured.md)。

E03-A 最小评估：`uv run python -m hello_agent.sdk.e03_evaluation.agent`。复用 E01，运行六道固定题；逐题记录是否完成、是否通过短答案规则、答案、耗时和错误类型。共六次模型请求，不用模型自评。详见 [评估学习记录](docs/e03_evaluation.md)。

工具历史整轮预算实验：`uv run python -m hello_agent.sdk.e02_context.tool_budget --preview`，去掉 `--preview` 请求一次回答。调用与结果按 ID 校验并随整个用户轮次裁剪；不会重新执行预置工具。默认预算移除旧工具轮次，`BUDGET_CONTEXT_TOKENS=2000` 可保留本例全部历史。

E02-C：`uv run python -m hello_agent.sdk.e02_context.budget --preview` 预览预算，去掉 `--preview` 发起一次请求。使用 `BUDGET_CONTEXT_TOKENS`、`BUDGET_OUTPUT_TOKENS`、`BUDGET_SAFETY_TOKENS` 配置本地估算额度；超过输入额度裁掉最早完整轮次，输出预留传为 `max_tokens`。估算不等于实际 token，详见 E02 学习记录。

E02-B 摘要对照入口：`uv run python -m hello_agent.sdk.e02_context.summary`。默认共 4 次模型请求，日志展示旧历史、模型生成的摘要与最终请求。原 E02-A 入口仍只比较全量与窗口。摘要可能遗漏或失真，且不保证比短原文更短，详见 [E02 学习记录](docs/e02_context.md)。

运行离线测试，无需调用真实模型服务：

```sh
uv run python -m unittest discover -s tests
```

测试使用受控响应，覆盖工具校验、循环停止、计划修正、检查修改、角色交接、响应清理，以及会话历史、偏好管理与失败边界。最近一次 E01-C 实现后的完整离线测试集通过。

真实模型记录与离线测试分开维护：

- P4 与 P1 使用同一固定任务，均正确得到 `581`；P4 为 5 次模型请求、16.93 秒，P1 为 3 次、6.71 秒，均执行两次工具。单次耗时不代表稳定性能。
- E01-A 会话 A 的追问正确得到“青绿色”；新会话 B 回答“不知道”。共 3 次模型请求，没有工具执行。
- P3 的模型检查可能误判，不能用“检查通过”代替原始任务的事实验收。

更完整的输入、失败场景和观察结果见各学习文档。

## 代码组织

```text
src/hello_agent/
├── config/settings.py       # 统一初始化配置实例
├── schemas/                 # Pydantic 参数、结果、配置模型与工具 Schema
├── tools/                   # 共用加法与模型请求函数
└── sdk/
    ├── p00_basics/          # 单次调用与一次工具调用
    ├── p01_react/           # 工具循环
    ├── p02_plan_execute/    # 规划与执行
    ├── p03_reflection/      # 检查与修改
    ├── p04_multi_agent/     # 委派与返回
    └── e01_memory/          # 进程内文本会话
tests/                      # 离线受控响应测试
docs/                       # 需求、路线、进度和实验记录
```

当前直接依赖为 openai、logly、Pydantic、pydantic-settings 和 MCP SDK，由 uv 管理。业务模块导入 schemas 中的数据定义，共用工具放在 tools 中；各学习入口保留为独立示例。

## 学习文档

- [需求文档](docs/requirements.md)：项目目标、范围与验收原则。
- [技术学习路线](docs/technical-roadmap.md)：P0–P4 与框架对照安排。
- [任务清单](docs/tasks.md)：当前阶段、待办和验证记录。
- [SDK 扩展学习计划](docs/sdk-learning-plan.md)：E01–E13 的顺序与最小实验。
- [协作约定](AGENTS.md)：代码组织、依赖选择与学习节奏。
