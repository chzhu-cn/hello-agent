"""P0：一轮工具执行，最多两次模型请求。"""

import argparse

from logly import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import ValidationError

from hello_agent.config.settings import llm_config
from hello_agent.schemas.tools import ADD_TOOL, AddArguments, AddResult
from hello_agent.tools.arithmetic import add

config = llm_config


def run(client: OpenAI, prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    logger.info("步骤 1：向模型提供 add 工具，等待回答或工具请求。")
    response = client.chat.completions.create(
        model=config.model, messages=messages, tools=[ADD_TOOL], tool_choice="auto",
    )
    if not response.choices:
        raise ValueError("模型响应没有 choices。")
    message = response.choices[0].message
    if message.tool_calls:
        # P0 只接受一个调用；P1 再支持多工具与循环。
        if len(message.tool_calls) != 1:
            raise ValueError("本示例只支持一次工具调用，本轮未执行任何工具。")
        call = message.tool_calls[0]
        if call.type != "function" or call.function.name != "add":
            raise ValueError("模型请求了未注册的工具，本轮未执行。")
        if not call.id:
            raise ValueError("工具调用缺少 ID，无法关联结果。")
        arguments = AddArguments.model_validate_json(call.function.arguments)
        logger.info("步骤 2：执行 add，调用 ID：{}，参数：{}", call.id, arguments)
        result = AddResult(result=add(arguments.a, arguments.b))
        logger.info("工具结果：{}", result.result)
        # 保留 assistant 的工具请求，再用同一个 ID 回传结果。
        messages.append(message.model_dump(exclude_none=True))
        messages.append({
            "role": "tool", "tool_call_id": call.id,
            "content": result.model_dump_json(),
        })
        logger.info("步骤 3：回传工具结果，请求最终回答。")
        response = client.chat.completions.create(
            model=config.model, messages=messages,
            tools=[ADD_TOOL], tool_choice="none",
        )
        if not response.choices:
            raise ValueError("第二次响应没有 choices。")
        message = response.choices[0].message
        if message.tool_calls:
            raise ValueError("模型再次请求工具，已达到本示例执行边界。")
    else:
        logger.info("模型直接回答，未执行工具。")
    if response.choices[0].finish_reason != "stop":
        raise ValueError("模型未正常完成回答，请检查停止原因或服务兼容性。")
    if not message.content or not message.content.strip():
        raise ValueError("模型没有返回可用文本。")
    logger.success("最终回答：\n{}", message.content)
    return message.content


def main() -> None:
    parser = argparse.ArgumentParser(description="体验一次加法工具调用")
    parser.add_argument(
        "prompt", nargs="?", default="请使用工具计算 127 加 358。",
    )
    args = parser.parse_args()
    if not args.prompt.strip() or config.base_url is None:
        logger.error("输入不能为空，且需要配置 LLM_BASE_URL。")
        raise SystemExit(1)
    try:
        with OpenAI(
            api_key=config.api_key.get_secret_value(),
            base_url=str(config.base_url), timeout=config.timeout, max_retries=0,
        ) as client:
            run(client, args.prompt)
    except ValidationError:
        logger.error("工具参数无效：需要两个范围内的数字 a、b，不允许额外字段。")
        raise SystemExit(1) from None
    except APITimeoutError:
        logger.error("模型请求超时。")
        raise SystemExit(1) from None
    except APIConnectionError:
        logger.error("无法连接模型服务。")
        raise SystemExit(1) from None
    except APIStatusError as exc:
        logger.error("模型服务返回 HTTP {}。", exc.status_code)
        raise SystemExit(1) from None
    except ValueError as exc:
        logger.error("{}", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
