"""以完整用户轮次为裁剪单位，工具调用及结果不可拆分。"""

import json

from hello_agent.schemas.config import BudgetConfig
from hello_agent.schemas.memory import ConversationMessage
from hello_agent.schemas.tool_history import ToolHistory


def tool_history_messages(history: ToolHistory) -> list[dict]:
    validated = ToolHistory.model_validate(history.model_dump())
    messages = []
    for turn in validated.turns:
        messages.append({"role": "user", "content": turn.user})
        for exchange in turn.exchanges:
            messages.append({
                "role": "assistant", "content": exchange.content,
                "tool_calls": [call.model_dump() for call in exchange.calls],
            })
            messages.extend(result.model_dump() for result in exchange.results)
        messages.append({"role": "assistant", "content": turn.answer})
    return messages


def estimate_tool_tokens(messages: list[dict]) -> int:
    # 将调用名称、参数、ID、结果等整个消息载荷纳入估算；仍非精确 token。
    payload = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    return len(payload.encode("utf-8")) + 16 * len(messages) + 3


def budget_tool_history(
    history: ToolHistory, prompt: str, system_prompt: str, budget: BudgetConfig,
) -> list[dict]:
    remaining = ToolHistory.model_validate(history.model_dump())
    question = ConversationMessage(role="user", content=prompt.strip()).model_dump()
    limit = budget.context_tokens - budget.output_tokens - budget.safety_tokens
    while True:
        messages = [
            {"role": "system", "content": system_prompt},
            *tool_history_messages(remaining), question,
        ]
        if estimate_tool_tokens(messages) <= limit:
            return messages
        if not remaining.turns:
            raise ValueError("系统说明与当前问题超过估算预算")
        remaining.turns.pop(0)
