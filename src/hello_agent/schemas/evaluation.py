"""E03 最小固定题目与评估结果。"""

from pydantic import BaseModel, Field

from hello_agent.schemas.memory import Conversation


class EvaluationCase(BaseModel):
    name: str
    history: Conversation = Field(default_factory=Conversation)
    question: str
    expected: str


class EvaluationResult(BaseModel):
    name: str
    expected: str
    answer: str | None = None
    completed: bool
    passed: bool
    error: str | None = None
    requests: int
    tool_calls: int = 0
    elapsed_seconds: float
