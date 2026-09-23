"""E05：模型请求工具，由客户端转发给本地 MCP 服务。"""

import asyncio
import sys
from datetime import timedelta
from typing import cast

from logly import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from hello_agent.schemas.mcp_tools import MCP_ARGUMENTS, MCPTool


async def run(client: AsyncOpenAI, session: ClientSession, model: str, prompt: str) -> str:
    discovered = (await session.list_tools()).tools
    if not discovered:
        raise ValueError("MCP 服务未提供工具")
    mcp_tools = [MCPTool(tool=tool) for tool in discovered]
    tools = [tool.model_tool() for tool in mcp_tools]
    names = {tool.name for tool in discovered}
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
    response = await client.chat.completions.create(
        model=model, messages=messages, tools=tools, tool_choice="auto",
    )
    if not response.choices:
        raise ValueError("模型响应没有 choices")
    message = response.choices[0].message
    if message.tool_calls:
        if response.choices[0].finish_reason != "tool_calls":
            raise ValueError("模型工具请求未完整结束")
        if len(message.tool_calls) != 1:
            raise ValueError("本步只接受一次工具调用，未执行工具")
        call = message.tool_calls[0]
        if call.type != "function" or call.function.name not in names:
            raise ValueError("模型请求了未发现的工具")
        if not call.id:
            raise ValueError("工具调用缺少 ID")
        arguments = MCP_ARGUMENTS.validate_json(call.function.arguments)
        logger.info("转发 MCP 工具：{}；调用 ID：{}", call.function.name, call.id)
        result = await session.call_tool(call.function.name, arguments)
        # 保留 isError、文本和结构化内容，让模型看到协议返回的真实结果。
        messages.append(cast(ChatCompletionMessageParam, message.model_dump(exclude_none=True)))
        messages.append({
            "role": "tool", "tool_call_id": call.id,
            "content": result.model_dump_json(exclude_none=True),
        })
        logger.info("MCP 已返回；isError：{}", result.isError)
        response = await client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="none",
        )
        if not response.choices:
            raise ValueError("第二次响应没有 choices")
        message = response.choices[0].message
    if message.tool_calls or response.choices[0].finish_reason != "stop":
        raise ValueError("模型未正常结束，或再次请求工具")
    if not message.content or not message.content.strip():
        raise ValueError("模型没有返回可用文本")
    logger.success("最终回答：{}", message.content)
    return message.content


async def main() -> None:
    from hello_agent.config.settings import llm_config

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "hello_agent.sdk.e05_mcp.server"],
    )
    async with AsyncOpenAI(
        api_key=llm_config.api_key.get_secret_value(),
        base_url=str(llm_config.base_url) if llm_config.base_url else None,
        timeout=llm_config.timeout, max_retries=0,
    ) as client:
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=10),
            ) as session:
                await session.initialize()
                await run(client, session, llm_config.model, "请使用工具计算 127 加 358。")


if __name__ == "__main__":
    asyncio.run(main())
