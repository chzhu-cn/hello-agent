"""E02-B：全量、窗口与旧历史摘要对照。"""

from time import perf_counter

from logly import logger
from openai import APIError, OpenAI

from hello_agent.config.settings import context_config, llm_config
from hello_agent.schemas.context import ContextPolicy
from hello_agent.sdk.e02_context.agent import QUESTION, SYSTEM_PROMPT, compare, example_history
from hello_agent.tools.llm import request_text
from hello_agent.tools.summary import summary_messages


def main() -> None:
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL。")
        raise SystemExit(1)
    history = example_history()
    failed = False
    with OpenAI(
        api_key=llm_config.api_key.get_secret_value(), base_url=str(llm_config.base_url),
        timeout=llm_config.timeout, max_retries=0,
    ) as client:
        try:
            compare(client, history)
        except SystemExit:
            failed = True
        started = perf_counter()
        try:
            messages = summary_messages(
                client, history, QUESTION, SYSTEM_PROMPT,
                ContextPolicy(mode="window", recent_turns=context_config.recent_turns),
            )
            for index, message in enumerate(messages):
                logger.info("摘要策略回答请求 {} [{}]：{}", index, message["role"], message["content"])
            logger.info("回答请求共 {} 条消息，正文 {} 字符（非 token）。", len(messages), sum(len(m["content"]) for m in messages))
            answer = request_text(client, messages)
            logger.success("summary 回复：{}", answer)
            logger.info("摘要策略总耗时 {:.2f} 秒（含摘要生成）。", perf_counter() - started)
        except (APIError, ValueError) as exc:
            failed = True
            logger.error("摘要策略失败（{}），不重试，不用原文偷偷替代摘要。", type(exc).__name__)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
