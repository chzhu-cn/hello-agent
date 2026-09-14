"""环境配置模型与校验约束。"""

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseSettings):
    """通过 LLM_ 前缀的环境变量或 .env 加载配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LLM_",
        extra="ignore",
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )

    model: str = Field(min_length=1, description="模型名称")
    api_key: SecretStr = Field(min_length=1, description="模型服务的 API Key")
    base_url: HttpUrl | None = Field(
        default=None, description="留空时使用 SDK 默认地址"
    )
    timeout: float = Field(
        default=30.0, gt=0, allow_inf_nan=False, description="请求超时，单位秒"
    )


class AgentConfig(BaseSettings):
    """Agent 执行限制，每一步表示一次模型请求。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="AGENT_",
        extra="ignore", hide_input_in_errors=True,
    )

    max_steps: int = Field(default=5, ge=1, le=100)


class PlanningConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="PLAN_",
        extra="ignore", hide_input_in_errors=True,
    )

    max_steps: int = Field(default=5, ge=1, le=100)
    max_repairs: int = Field(default=1, ge=0, le=2)


class ReflectionConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="REFLECTION_",
        extra="ignore", hide_input_in_errors=True,
    )

    max_revisions: int = Field(default=1, ge=0, le=2)
