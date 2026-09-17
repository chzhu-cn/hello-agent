"""共用的文本响应请求与完整性检查。"""

import re

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from logly import logger

from hello_agent.config.settings import llm_config


def _strip_think(text: str) -> str:
    """仅移除响应开头完整的 think 块，保留正文中的字面内容。"""
    text = text.strip()
    while re.match(r"<think\s*>", text, flags=re.IGNORECASE):
        block = re.match(r"<think\s*>.*?</think\s*>", text, flags=re.IGNORECASE | re.DOTALL)
        if block is None:
            raise ValueError("模型的 think 块未闭合。")
        text = text[block.end():].strip()
    if not text:
        raise ValueError("模型返回空文本，未提供正文。")
    return text


def _clean_response(text: str) -> str:
    """移除外围 think 与单个 JSON 代码围栏，不修补 JSON 字段。"""
    text = _strip_think(text)
    fenced = re.fullmatch(
        r"(?P<fence>`{2,}|~{3,})(?:json)?\s*(?P<body>.*?)\s*(?P=fence)",
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    text = fenced.group("body").strip() if fenced else text
    if not text:
        raise ValueError("模型返回空文本，未提供正文。")
    return text


def request_message(client: OpenAI, messages: list, tools: list | None = None, *, max_tokens: int | None = None) -> ChatCompletionMessage:
    options = {"tools": tools, "tool_choice": "auto"} if tools else {}
    if max_tokens is not None:
        options["max_tokens"] = max_tokens
    response = client.chat.completions.create(model=llm_config.model, messages=messages, **options)
    if max_tokens is not None:
        logger.info("服务返回 usage：{}", response.usage.model_dump_json() if response.usage else "未提供")
    if not response.choices:
        raise ValueError("模型未返回 choices。")
    choice = response.choices[0]
    message = choice.message
    if message.tool_calls:
        if not tools or choice.finish_reason != "tool_calls":
            raise ValueError("模型没有正常完成工具响应。")
        return message
    if choice.finish_reason != "stop":
        raise ValueError("模型没有正常完成文本响应。")
    text = message.content
    if not text or not text.strip():
        raise ValueError("模型返回空文本。")
    return message.model_copy(update={"content": _clean_response(text)})


def request_text(client: OpenAI, messages: list, *, max_tokens: int | None = None) -> str:
    return request_message(client, messages, max_tokens=max_tokens).content
