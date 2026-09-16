"""E02-A：文本历史选择策略。"""

from typing import Literal

from pydantic import BaseModel, Field


class ContextPolicy(BaseModel):
    mode: Literal["full", "window"]
    recent_turns: int = Field(default=2, ge=0, le=100)
