"""统一加载配置并提供模块级实例。"""

from logly import logger

from hello_agent.schemas.config import LLMConfig
from hello_agent.schemas.config import AgentConfig, PlanningConfig
from hello_agent.schemas.config import ReflectionConfig


llm_config = LLMConfig()
logger.success("Successfully load LLM config: {}", llm_config)

agent_config = AgentConfig()
logger.success("Successfully load agent config: {}", agent_config)


planning_config = PlanningConfig()
logger.success("Successfully load planning config: {}", planning_config)

reflection_config = ReflectionConfig()
logger.success("Successfully load reflection config: {}", reflection_config)
