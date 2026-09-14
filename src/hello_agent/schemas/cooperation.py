"""角色交接与实际运行记录。"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hello_agent.schemas.tools import AddArguments


class Delegation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    recipient: Literal["calculator"]
    instruction: str = Field(min_length=1)


class ToolRecord(BaseModel):
    tool: Literal["add"] = "add"
    arguments: AddArguments
    result: float = Field(allow_inf_nan=False)


class WorkerResult(BaseModel):
    status: Literal["completed", "failed"]
    answer: str = ""
    records: list[ToolRecord] = Field(default_factory=list)
    error: str | None = None
    model_requests: int = Field(ge=0)

    @model_validator(mode="after")
    def check_status(self) -> Self:
        if self.status == "completed":
            if not self.answer.strip() or not self.records or self.error is not None:
                raise ValueError("完成结果必须包含答案和实际工具记录，且没有错误。")
        elif not self.error or not self.error.strip():
            raise ValueError("失败结果必须包含原因。")
        return self


class CooperationResult(BaseModel):
    status: Literal["completed", "failed"]
    answer: str = ""
    error: str | None = None
    delegation: Delegation | None = None
    worker: WorkerResult | None = None
    coordinator_requests: int
    total_requests: int
    elapsed_seconds: float
