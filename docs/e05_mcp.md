# E05-A：本地 MCP 工具发现与调用

运行客户端，它会自动启动并关闭服务子进程，无需另开终端：

```sh
uv run python -m hello_agent.sdk.e05_mcp.client
```

本步固定调用 add(127, 358)，预期结果 485；不调用模型，不需要 API 密钥，不监听网络端口。

## 数据如何流动

客户端启动 server 模块 → initialize 建立协议会话 → list_tools 获取工具名称、说明和参数 Schema → call_tool 发送名称与参数 → 服务校验参数并执行现有 add → 客户端校验结构和计算结果。

过去是当前 Python 进程直接调用 add；现在 add 在另一个进程中执行，两端通过标准输入和标准输出传递 MCP 消息。服务端 stdout 必须留给协议，所以没有导入会产生日志的模型配置模块。客户端使用 logly 展示工具名和数值，避免数组日志显示问题。

输入与结果约束复用 schemas/tools.py 中的 Pydantic 模型，MCP 工具声明放在 schemas/mcp_tools.py。使用协议 SDK 的 Server 注册两个处理函数，便于复用现有平铺参数 Schema，不引入 Agent 框架。依赖固定在 MCP SDK 1.x 系列，当前锁定 1.30.0；实现依据该版本源码及 [官方 v1 文档](https://py.sdk.modelcontextprotocol.io/v1/)，不混用 v2 接口。

## 验证（2026-09-23）

- Python 3.14 环境安装成功，真实 stdio 子进程发现 add 并返回 485.0。
- uv 安装使用 PyPI 默认源，锁文件同步更新来源；尝试保留原清华镜像时连接超时，因此保留已成功解析的 PyPI 锁文件。
- 新增 1 项集成测试：发现工具、正确求和、未知工具、错误类型、缺少字段、多余字段、超出数值范围；错误返回 isError，随后同一会话仍可正确得到 5.0。
- 全套 91 项测试通过，无真实模型请求。

工具调用错误通过 isError 返回，连接故障则可能直接抛出异常。客户端设定单次请求等待上限 10 秒；此上限不等于整个子进程生命周期的总时限。服务突然断开和执行函数内部异常尚未实验，不能将参数错误测试视作这两项验证。

## 模型接入（2026-09-23）

```sh
uv run python -m hello_agent.sdk.e05_mcp.agent
```

此入口使用现有 `.env` 模型配置。原 client 入口仍可独立运行。

数据流：list_tools → 将 name、description、inputSchema 转为模型 tools → 模型返回工具调用 → 校验名称、ID 和 JSON 对象 → MCP call_tool → 保留 assistant 调用及同一 tool_call_id 的结果消息 → 模型回答。

关键区别：模型只生成工具名称和参数；我们的客户端负责连接 MCP 服务；服务端校验 add 参数并执行 Python 函数。工具声明从服务发现，不在模型入口重复手写 add Schema。

本步最多一次工具调用、两次模型请求。MCP 的 isError、content 和 structuredContent 一起回传，让模型知道失败；连接异常直接向上传播，不自动重试。该示例只面向本地 add 服务，尚未扩展分页发现、多模态结果与多工具循环。

新增 4 项受控测试，覆盖声明转换、ID 关联、成功与错误结果、直接回答、非法调用拒绝、连接异常不重试；全套 95 项测试通过。受控 ConnectionError 不等于真实服务断开实验，真实断开与服务内部执行异常仍待下一步验证。学习理解仍待回顾，整个 E05 保留未完成。

真实模型验证：使用当前配置的 gemini-2.5-flash，模型请求 add，MCP 返回 isError=False，第二次模型请求最终回答 485，进程正常退出。共两次模型请求、一次 MCP 工具调用。
