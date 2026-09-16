"""E02-A：对同一份预置历史比较全量与最近几轮。"""

import argparse
from time import perf_counter

from logly import logger
from openai import APIError, OpenAI

from hello_agent.config.settings import context_config, llm_config
from hello_agent.schemas.context import ContextPolicy
from hello_agent.schemas.memory import Conversation, ConversationMessage
from hello_agent.tools.context import build_messages
from hello_agent.tools.llm import request_text

SYSTEM_PROMPT = "仅根据本次提供的对话回答。没有明确依据时说不知道，不猜测用户偏好。用简短中文回答。"
QUESTION = "我最喜欢的颜色是什么？"


def example_history() -> Conversation:
    # 人工预置的四轮文本，两个策略使用同一份，不消耗模型请求生成历史。
    turns = [
        ("本次虚构示例中，我最喜欢的颜色是青绿色。", "知道了，你最喜欢青绿色。"),
        ("今天练习加法，2 加 3 等于多少？", "等于 5。"),
        ("把 hello 翻译成中文。", "你好。"),
        ("给我一个整理书桌的建议。", "把书本和文具分开摆放。"),
    ]
    return Conversation(messages=[
        message
        for user, assistant in turns
        for message in (
            ConversationMessage(role="user", content=user),
            ConversationMessage(role="assistant", content=assistant),
        )
    ])


def compare(client: OpenAI | None, history: Conversation) -> None:
    failed = False
    for mode in ("full", "window"):
        policy = ContextPolicy(mode=mode, recent_turns=context_config.recent_turns)
        messages = build_messages(history, QUESTION, SYSTEM_PROMPT, policy)
        logger.info(
            "策略 {}：原始历史 {} 轮，发送历史 {} 轮，总消息 {} 条，正文 {} 字符（非 token）。",
            mode, len(history.messages) // 2, (len(messages) - 2) // 2,
            len(messages), sum(len(message["content"]) for message in messages),
        )
        for index, message in enumerate(messages):
            logger.info("请求消息 {} [{}]：{}", index, message["role"], message["content"])
        if client is None:
            continue
        started = perf_counter()
        try:
            answer = request_text(client, messages)
            logger.success("{} 回复：{}", mode, answer)
            logger.info("{} 模型请求 1 次，耗时 {:.2f} 秒。", mode, perf_counter() - started)
        except (APIError, ValueError) as exc:
            failed = True
            logger.error("{} 请求失败（{}），不重试，继续独立对照。", mode, type(exc).__name__)
    if failed:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="E02-A 全量历史与最近几轮对照")
    parser.add_argument("--preview", action="store_true", help="仅展示请求消息，不调用模型")
    args = parser.parse_args()
    history = example_history()
    if args.preview:
        compare(None, history)
        return
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL。")
        raise SystemExit(1)
    with OpenAI(
        api_key=llm_config.api_key.get_secret_value(), base_url=str(llm_config.base_url),
        timeout=llm_config.timeout, max_retries=0,
    ) as client:
        compare(client, history)


if __name__ == "__main__":
    main()
