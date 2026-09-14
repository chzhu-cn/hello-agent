"""E01-A：进程内文本会话的数据定义。"""

from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class Conversation(BaseModel):
    messages: list[ConversationMessage] = Field(default_factory=list)
