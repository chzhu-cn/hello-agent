"""E02-C：裁剪至本地估算预算，设置服务输出上限。"""

import argparse

from logly import logger
from openai import APIError, OpenAI

from hello_agent.config.settings import budget_config, llm_config
from hello_agent.schemas.context import ContextPolicy
from hello_agent.sdk.e02_context.agent import QUESTION, SYSTEM_PROMPT, example_history
from hello_agent.tools.budget import budget_messages, estimate_tokens
from hello_agent.tools.context import build_messages
from hello_agent.tools.llm import request_text


def main() -> None:
    parser = argparse.ArgumentParser(description="E02-C 本地估算预算与输出上限")
    parser.add_argument(
        "--preview", action="store_true", help="只查看预算和请求，不调用模型"
    )
    args = parser.parse_args()
    history = example_history()
    try:
        original = build_messages(
            history, QUESTION, SYSTEM_PROMPT, ContextPolicy(mode="full")
        )
        messages = budget_messages(history, QUESTION, SYSTEM_PROMPT, budget_config)
        logger.info(
            "本地估算：原始 {}，裁剪后 {}；输入预算 {} = 总预算 {} - 输出预留 {} - 余量 {}。",
            estimate_tokens(original),
            estimate_tokens(messages),
            budget_config.context_tokens
            - budget_config.output_tokens
            - budget_config.safety_tokens,
            budget_config.context_tokens,
            budget_config.output_tokens,
            budget_config.safety_tokens,
        )
        logger.info(
            "保留 {} 轮，移除 {} 轮；此估算不是模型精确 token 数。",
            (len(messages) - 2) // 2,
            (len(original) - len(messages)) // 2,
        )
        for index, message in enumerate(messages):
            logger.info("请求 {} [{}]：{}", index, message["role"], message["content"])
        if args.preview:
            return
        if llm_config.base_url is None:
            raise ValueError("请配置 LLM_BASE_URL")
        with OpenAI(
            api_key=llm_config.api_key.get_secret_value(),
            base_url=str(llm_config.base_url),
            timeout=llm_config.timeout,
            max_retries=0,
        ) as client:
            answer = request_text(
                client, messages, max_tokens=budget_config.output_tokens
            )
            logger.success("预算策略回复：{}", answer)
    except (APIError, ValueError) as exc:
        logger.error(
            "预算或请求失败（{}）：{}；不重试。",
            type(exc).__name__,
            str(exc) if isinstance(exc, ValueError) else "服务请求失败",
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
