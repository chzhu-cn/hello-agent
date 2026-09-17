"""E02-C：按本地估算裁剪完整文本轮次，不声称精确计数。"""

from hello_agent.schemas.config import BudgetConfig
from hello_agent.schemas.context import ContextPolicy
from hello_agent.schemas.memory import Conversation
from hello_agent.tools.context import build_messages


def estimate_tokens(messages: list[dict[str, str]]) -> int:
    # 启发式：正文 UTF-8 字节数 + 每条消息 16 + 请求 3。
    # 不是 Gemini tokenizer，也不保证是任意服务的 token 上界。
    return 3 + sum(len(m["content"].encode("utf-8")) + 16 for m in messages)


def budget_messages(
    history: Conversation, prompt: str, system_prompt: str, budget: BudgetConfig,
) -> list[dict[str, str]]:
    messages = build_messages(history, prompt, system_prompt, ContextPolicy(mode="full"))
    input_limit = budget.context_tokens - budget.output_tokens - budget.safety_tokens
    while estimate_tokens(messages) > input_limit and len(messages) > 2:
        del messages[1:3]
    if estimate_tokens(messages) > input_limit:
        raise ValueError("系统说明与当前问题已超过输入估算预算；请缩短输入或调整预算")
    return messages
