# Hello Agent

以 OpenAI 兼容接口体验一次模型调用。从项目根目录运行。

1. 安装依赖：`uv sync`。
2. 如果没有 `.env`，复制 `.env.example` 为 `.env`；已有文件直接编辑，不要覆盖。
3. 填写服务提供的 `LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_API_KEY`。基础地址不要包含 `/chat/completions`；示例域名需要替换。`LLM_TIMEOUT` 默认 30 秒。
4. 运行：

```sh
uv run hello-agent
# 或提供自己的输入
uv run hello-agent "用一句话解释什么是工具调用"
```

程序发送一条用户消息，等待完整回复，通过 logly 输出后退出。没有多轮历史或工具调用；关闭 SDK 自动重试。配置在模块导入时统一初始化，配置无效时由 Pydantic 直接报告；请求失败或没有文本时以状态码 1 退出。

调用入口：`src/hello_agent/sdk/p00_basics/single_call.py`。

2026-09-13：Python 3.14 环境已安装 openai 3.13.0。用户确认修改后的代码已跑通真实模型调用；此前已验证受控响应的文本提取与空响应退出。具体模型与回复原文未收录。

## 体验加法工具

使用同一份 `.env` 配置运行：

```sh
uv run python -m hello_agent.sdk.p00_basics.tool_call
```

默认请求模型使用工具计算 127 + 358。日志依次显示模型请求、Python 执行参数与结果、模型最终回答。仅支持一个工具调用，最多两次模型请求。

离线验证：`uv run python -m unittest discover -s tests`。
