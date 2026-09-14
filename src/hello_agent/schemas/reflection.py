"""P3 的事实记录、检查反馈与运行结果。"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hello_agent.schemas.tools import AddArguments


class CalculationRecord(BaseModel):
    arguments: AddArguments
    result: float


class Critique(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    passed: bool
    issues: list[str] = Field(description="可核对的问题与具体修改建议；通过时为空")

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        if self.passed == bool(self.issues) or any(not issue for issue in self.issues):
            raise ValueError("通过时 issues 必须为空；未通过时必须提供非空问题。")
        return self


class ReflectionResult(BaseModel):
    answer: str
    critique: Critique
    revisions: int
    requests: int
    tool_calls: int
    elapsed_seconds: float
    stop_reason: Literal["passed", "revision_limit"]
