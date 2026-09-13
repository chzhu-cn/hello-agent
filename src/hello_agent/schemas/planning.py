"""计划、步骤引用与执行记录。"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Number = Annotated[float, Field(ge=-1e100, le=1e100)]


class StepReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    step: str = Field(min_length=1)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    id: str = Field(min_length=1)
    tool: Literal["add"]
    a: Number | StepReference
    b: Number | StepReference


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    steps: list[PlanStep]

    @model_validator(mode="after")
    def validate_dependencies(self):
        seen = set()
        for step in self.steps:
            if step.id in seen:
                raise ValueError("步骤 ID 不可重复")
            for operand in (step.a, step.b):
                if isinstance(operand, StepReference) and operand.step not in seen:
                    raise ValueError("只能引用已排在前面的步骤")
            seen.add(step.id)
        return self


class StepResult(BaseModel):
    step: str
    result: float
