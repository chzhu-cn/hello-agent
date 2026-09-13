"""P0：一次同步、非流式的 Chat Completions 调用。"""

import argparse

from logly import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from hello_agent.config.settings import llm_config

config = llm_config


def main() -> None:
    parser = argparse.ArgumentParser(description="通过 OpenAI 兼容接口发送一次文本请求")
    parser.add_argument(
        "prompt", nargs="?", default="请用一句中文解释什么是 AI Agent。"
    )
    args = parser.parse_args()
    if not args.prompt.strip():
        logger.error("输入不能为空。")
        raise SystemExit(1)

    if config.base_url is None:
        logger.error("请在 .env 中填写兼容服务的 LLM_BASE_URL（API 基础地址）。")
        raise SystemExit(1)

    logger.info("开始请求，模型：{}", config.model)
    try:
        with OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=str(config.base_url),
            timeout=config.timeout,
            max_retries=0,
        ) as client:
            response = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "user", "content": args.prompt}],
            )
    except APITimeoutError:
        logger.error("模型请求超时，请检查服务或调整 LLM_TIMEOUT。")
        raise SystemExit(1) from None
    except APIConnectionError:
        logger.error("无法连接模型服务，请检查网络和 LLM_BASE_URL。")
        raise SystemExit(1) from None
    except APIStatusError as exc:
        logger.error(
            "模型服务返回 HTTP {}，请检查认证、模型名称与服务状态。", exc.status_code
        )
        raise SystemExit(1) from None

    if not response.choices or not response.choices[0].message.content:
        logger.error("响应没有可用文本，请检查服务的 Chat Completions 兼容性。")
        raise SystemExit(1)
    reply = response.choices[0].message.content
    if not reply.strip():
        logger.error("模型返回了空白文本。")
        raise SystemExit(1)
    logger.success("模型回复：\n{}", reply)
    logger.info("停止原因：{}", response.choices[0].finish_reason)
    if response.usage is not None:
        logger.info("Token 用量：{}", response.usage.total_tokens)


if __name__ == "__main__":
    main()
