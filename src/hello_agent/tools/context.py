"""选择完整文本轮次，不修改保存的原始历史。"""

from hello_agent.schemas.context import ContextPolicy
from hello_agent.schemas.memory import Conversation, ConversationMessage


def split_history(history: Conversation, policy: ContextPolicy) -> tuple[Conversation, Conversation]:
    validated = Conversation.model_validate(history.model_dump())
    cut = max(0, len(validated.messages) - 2 * policy.recent_turns)
    return Conversation(messages=validated.messages[:cut]), Conversation(messages=validated.messages[cut:])


def build_messages(
    history: Conversation, prompt: str, system_prompt: str, policy: ContextPolicy,
) -> list[dict[str, str]]:
    question = ConversationMessage(role="user", content=prompt.strip())
    # 再校验可变列表，避免外部追加半轮消息后静默截断。
    validated = Conversation.model_validate(history.model_dump())
    selected = validated.messages
    if policy.mode == "window":
        selected = selected[-2 * policy.recent_turns:] if policy.recent_turns else []
    return [
        {"role": "system", "content": system_prompt},
        *[message.model_dump() for message in selected],
        question.model_dump(),
    ]
