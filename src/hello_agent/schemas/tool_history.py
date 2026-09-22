"""E02：按完整用户轮次保存文本及工具调用记录。"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RecordedFunction(BaseModel):
    name: str = Field(min_length=1)
    arguments: str = Field(min_length=1)


class RecordedCall(BaseModel):
    id: str = Field(min_length=1)
    type: Literal["function"] = "function"
    function: RecordedFunction


class RecordedResult(BaseModel):
    role: Literal["tool"] = "tool"
    tool_call_id: str = Field(min_length=1)
    content: str


class ToolExchange(BaseModel):
    calls: list[RecordedCall] = Field(min_length=1)
    results: list[RecordedResult] = Field(min_length=1)
    content: str | None = None

    @model_validator(mode="after")
    def matching_results(self) -> "ToolExchange":
        calls = [call.id for call in self.calls]
        results = [result.tool_call_id for result in self.results]
        if (
            len(set(calls)) != len(calls)
            or len(set(results)) != len(results)
            or set(calls) != set(results)
        ):
            raise ValueError("工具调用 ID 必须唯一，且每个调用恰好对应一个结果")
        return self


class CompletedToolTurn(BaseModel):
    user: str = Field(min_length=1)
    exchanges: list[ToolExchange] = Field(default_factory=list)
    answer: str = Field(min_length=1)


class ToolHistory(BaseModel):
    turns: list[CompletedToolTurn] = Field(default_factory=list)
