"""P1：请求模型、执行工具、回传结果，直到回答或达到步数上限。"""

import argparse

from logly import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI
from pydantic import ValidationError

from hello_agent.config.settings import llm_config, agent_config
from hello_agent.schemas.tools import ADD_TOOL, AddArguments, AddResult
from hello_agent.tools.arithmetic import add


def run(client: OpenAI, prompt: str) -> str:
    if not prompt.strip():
        raise ValueError("输入不能为空。")
    messages = [{"role": "user", "content": prompt}]
    for step in range(1, agent_config.max_steps + 1):
        logger.info("步骤 {}/{}：请求模型。", step, agent_config.max_steps)
        response = client.chat.completions.create(
            model=llm_config.model,
            messages=messages,
            tools=[ADD_TOOL],
            tool_choice="auto",
        )
        if not response.choices:
            raise ValueError("模型响应没有 choices。")
        choice = response.choices[0]
        message = choice.message
        if not message.tool_calls:
            if (
                choice.finish_reason != "stop"
                or not message.content
                or not message.content.strip()
            ):
                raise ValueError("模型未返回完整的最终回答。")
            logger.success("最终回答：\n{}", message.content)
            logger.info("停止原因：正常完成，共 {} 步。", step)
            return message.content
        if choice.finish_reason != "tool_calls":
            raise ValueError("工具请求未正常完成，本轮不执行工具。")
        # 最后一步没有剩余请求额度，不执行无法回传结果的新工具。
        if step == agent_config.max_steps:
            break
        validated = []
        ids = set()
        for call in message.tool_calls:
            if call.type != "function" or call.function.name != "add":
                raise ValueError("未知工具，本轮不执行任何工具。")
            if not call.id or call.id in ids:
                raise ValueError("工具调用 ID 缺失或重复，本轮不执行任何工具。")
            ids.add(call.id)
            arguments = AddArguments.model_validate_json(call.function.arguments)
            validated.append((call, arguments))
        messages.append(message.model_dump(exclude_none=True))
        # 先校验整轮，再按顺序执行所有调用，并分别关联结果。
        for call, arguments in validated:
            logger.info("执行工具 add，ID：{}，参数：{}", call.id, arguments)
            try:
                result = AddResult(result=add(arguments.a, arguments.b))
            except Exception:
                raise ValueError("add 执行失败，结束本次任务。") from None
            logger.info("工具结果：{}", result.result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.model_dump_json(),
                }
            )
    raise ValueError("达到最大模型请求步数，任务尚未完成。")


def main() -> None:
    parser = argparse.ArgumentParser(description="体验有步数限制的 Agent 循环")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="请先调用 add 计算 127 加 358，收到工具结果后再调用 add 将结果加上 96，最后回答。",
    )
    args = parser.parse_args()
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL。")
        raise SystemExit(1)
    try:
        with OpenAI(
            api_key=llm_config.api_key.get_secret_value(),
            base_url=str(llm_config.base_url),
            timeout=llm_config.timeout,
            max_retries=0,
        ) as client:
            run(client, args.prompt)
    except ValidationError:
        logger.error("停止原因：工具参数无效，本轮未执行工具。")
        raise SystemExit(1) from None
    except APITimeoutError:
        logger.error("停止原因：模型请求超时。")
        raise SystemExit(1) from None
    except APIConnectionError:
        logger.error("停止原因：无法连接模型服务。")
        raise SystemExit(1) from None
    except APIStatusError as exc:
        logger.error("停止原因：模型服务返回 HTTP {}。", exc.status_code)
        raise SystemExit(1) from None
    except ValueError as exc:
        logger.error("停止原因：{}", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
