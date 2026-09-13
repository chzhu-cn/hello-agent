"""统一加载配置并提供模块级实例。"""

from logly import logger

from hello_agent.schemas.config import LLMConfig
from hello_agent.schemas.config import AgentConfig


llm_config = LLMConfig()
logger.success("Successfully load LLM config: {}", llm_config)

agent_config = AgentConfig()
logger.success("Successfully load agent config: {}", agent_config)
