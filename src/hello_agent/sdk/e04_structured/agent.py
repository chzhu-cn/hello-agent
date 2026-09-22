"""E04-A：提示 JSON 与服务 Schema 参数对照，各发一次请求。"""

from logly import logger
from openai import APIError, OpenAI
from openai.types.chat import ChatCompletion
from openai.types.chat.completion_create_params import CompletionCreateParamsNonStreaming

from hello_agent.config.settings import llm_config
from hello_agent.schemas.structured import COLOR_RESPONSE_FORMAT, ColorPreference

TASK = "这件衣服是红色，但我最喜欢的颜色是青绿色。"
SYSTEM = (
    "从用户原文提取明确表达的最喜欢颜色，不把物品颜色当作偏好。"
    "只输出 JSON 对象，字段为 favorite_color，值为颜色名称字符串；未提供则为 null。"
    "不输出额外字段或 Markdown。"
)


def validate_response(response: ChatCompletion) -> ColorPreference:
    if not response.choices:
        raise ValueError("响应缺少 choices")
    choice = response.choices[0]
    if choice.message.refusal:
        raise ValueError("模型拒绝回答")
    if choice.finish_reason != "stop" or choice.message.tool_calls:
        raise ValueError("响应未正常结束或返回了工具调用")
    if not choice.message.content or not choice.message.content.strip():
        raise ValueError("响应正文为空")
    # 不剥离围栏或修补 JSON，观察服务原始输出是否符合约定。
    return ColorPreference.model_validate_json(choice.message.content)


def main() -> None:
    if llm_config.base_url is None:
        logger.error("请配置 LLM_BASE_URL")
        raise SystemExit(1)
    failed = False
    with OpenAI(
        api_key=llm_config.api_key.get_secret_value(),
        base_url=str(llm_config.base_url),
        timeout=llm_config.timeout,
        max_retries=0,
    ) as client:
        for mode in ("prompt", "schema"):
            options: CompletionCreateParamsNonStreaming = {
                "model": llm_config.model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": TASK},
                ],
            }
            if mode == "schema":
                options["response_format"] = COLOR_RESPONSE_FORMAT
            print("COLOR_RESPONSE_FORMAT: ", COLOR_RESPONSE_FORMAT)
            try:
                response = client.chat.completions.create(
                    **options,
                )
                result = validate_response(response)
                correct = result.favorite_color == "青绿色"
                logger.info(
                    "模式 {}：结构校验通过，favorite_color={}，事实验收={}。",
                    mode,
                    result.favorite_color,
                    correct,
                )
                if not correct:
                    failed = True
            except APIError as exc:
                failed = True
                logger.error(
                    "模式 {}：请求失败，类型 {}，HTTP {}；不自动降级。",
                    mode,
                    type(exc).__name__,
                    getattr(exc, "status_code", None),
                )
            except ValueError as exc:
                failed = True
                logger.error(
                    "模式 {}：响应校验失败，类型 {}。", mode, type(exc).__name__
                )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
