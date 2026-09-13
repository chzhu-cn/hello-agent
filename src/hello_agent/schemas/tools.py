"""工具参数、结果模型与提供给模型的工具 Schema。"""

from pydantic import BaseModel, ConfigDict, Field


class AddArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    a: float = Field(description="第一个加数", ge=-1e100, le=1e100)
    b: float = Field(description="第二个加数", ge=-1e100, le=1e100)


class AddResult(BaseModel):
    result: float


ADD_TOOL = {
    "type": "function",
    "function": {
        "name": "add",
        "description": "计算两个数字的和。使用浮点运算，不适用于精确财务计算。",
        "parameters": AddArguments.model_json_schema(),
    },
}
