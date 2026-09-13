# 项目协作规则

1. 开展项目工作前，阅读 [需求文档](docs/requirements.md)，并在讨论、设计和实现中考虑其中的学习目标、范围、阶段安排与验收标准。
2. 日志统一使用 `logly`，不使用 `print`。
3. HTTP 客户端使用 `httpx` 或 `requests`。
4. 需要开发 Web 服务时，使用 `FastAPI`。
5. 开始项目工作前，查看 [任务清单](docs/tasks.md)，确认当前阶段和下一步；完成任务后，按实际完成情况更新清单与当前进度。每次只推进当前约定的学习步骤。
6. 数据模型与数据约束统一使用 `Pydantic`，不使用 `dataclass`。
7. 配置统一使用 `.env` 与 `pydantic-settings` 加载和校验。

## 已确认的代码偏好

- 配置在配置模块中统一创建模块级实例（如 `llm_config = LLMConfig()`），业务模块直接导入复用。
- 当前学习示例保持直接、简洁；配置无效时由 Pydantic 在初始化时报告，不额外包装一层字段错误处理。
- 配置加载成功使用 logly 记录；密钥保持 SecretStr 脱敏，不调用 get_secret_value() 写入日志。
- 保留用户调整后的多行参数排版，避免无关的风格重写。

- 所有 Schema（参数、结果、配置等 Pydantic 模型及工具 JSON Schema）统一放在 `src/hello_agent/schemas/` 下，按功能归类；业务文件仅导入使用，不内嵌定义。配置实例仍在配置模块中统一初始化。
