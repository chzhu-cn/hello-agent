"""统一加载配置并提供模块级实例。"""

from logly import logger

from hello_agent.schemas.config import LLMConfig


llm_config = LLMConfig()
logger.success("Successfully load LLM config: {}", llm_config)
