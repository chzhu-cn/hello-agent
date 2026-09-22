"""E02：预置工具历史的整轮裁剪；不重新执行历史工具。"""

import argparse
import json

from logly import logger
from openai import APIError, OpenAI

from hello_agent.config.settings import budget_config, llm_config
from hello_agent.schemas.tool_history import ToolHistory
from hello_agent.tools.tool_context import budget_tool_history, estimate_tool_tokens
from hello_agent.tools.llm import request_text


def example_history() -> ToolHistory:
    return ToolHistory.model_validate(
        {
            "turns": [
                {
                    "user": "分别计算 2+3 和 4+5。",
                    "exchanges": [
                        {
                            "calls": [
                                {
                                    "id": "add_1",
                                    "function": {
                                        "name": "add",
                                        "arguments": '{"a":2,"b":3}',
                                    },
                                },
                                {
                                    "id": "add_2",
                                    "function": {
                                        "name": "add",
                                        "arguments": '{"a":4,"b":5}',
                                    },
                                },
                            ],
                            "results": [
                                {"tool_call_id": "add_1", "content": '{"result":5}'},
                                {"tool_call_id": "add_2", "content": '{"result":9}'},
                            ],
                        }
                    ],
                    "answer": "结果分别是 5 和 9。",
                },
                {"user": "你好", "answer": "你好。"},
            ]
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="完整工具历史预算实验")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    try:
        prompt = "刚才两次计算的结果是什么？"
        system_prompt = "仅根据历史回答，历史没有记录时说不知道。"
        messages = budget_tool_history(
            example_history(),
            prompt,
            system_prompt,
            budget_config,
        )
        logger.info(
            "预置历史不执行工具；整轮裁剪后本地估算 {}，消息 {} 条。",
            estimate_tool_tokens(messages),
            len(messages),
        )
        logger.info("实际请求消息：{}", json.dumps(messages, ensure_ascii=False))
        print(f"实际请求消息：{json.dumps(messages, ensure_ascii=False)}")
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
            logger.success(
                "回复：{}",
                request_text(client, messages, max_tokens=budget_config.output_tokens),
            )
    except (APIError, ValueError) as exc:
        logger.error("工具历史实验失败（{}），不重试。", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
