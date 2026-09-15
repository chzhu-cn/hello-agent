"""E01-A：进程内文本会话的数据定义。"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class Conversation(BaseModel):
    messages: list[ConversationMessage] = Field(default_factory=list)

    @model_validator(mode="after")
    def complete_turns(self) -> "Conversation":
        if len(self.messages) % 2 or any(
            message.role != ("user" if index % 2 == 0 else "assistant")
            for index, message in enumerate(self.messages)
        ):
            raise ValueError("历史必须由交替的 user、assistant 完整轮次组成")
        return self


class SessionKey(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
