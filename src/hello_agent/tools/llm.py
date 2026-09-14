"""共用的文本响应请求与完整性检查。"""

import re

from openai import OpenAI

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


def request_text(client: OpenAI, messages: list) -> str:
    response = client.chat.completions.create(model=llm_config.model, messages=messages)
    if not response.choices:
        raise ValueError("模型未返回 choices。")
    choice = response.choices[0]
    if choice.finish_reason != "stop" or choice.message.tool_calls:
        raise ValueError("模型没有正常完成文本响应。")
    text = choice.message.content
    if not text or not text.strip():
        raise ValueError("模型返回空文本。")
    return _clean_response(text)
