"""启动本地子进程，真实发现并调用 MCP 工具；不请求模型。"""

import asyncio
import sys
from datetime import timedelta

from logly import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from hello_agent.schemas.tools import AddArguments, AddResult


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "hello_agent.sdk.e05_mcp.server"],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, read_timeout_seconds=timedelta(seconds=10)
        ) as session:
            await session.initialize()
            discovered = await session.list_tools()
            for tool in discovered.tools:
                logger.info("发现工具：{}；说明：{}", tool.name, tool.description)
            if not any(tool.name == "add" for tool in discovered.tools):
                raise ValueError("服务未提供 add 工具")
            args = AddArguments(a=127, b=358)
            response = await session.call_tool("add", args.model_dump())
            if response.isError:
                raise ValueError("MCP 工具执行失败")
            result = AddResult.model_validate(response.structuredContent)
            if result.result != 485:
                raise ValueError("工具返回值未通过事实验收")
            logger.success("MCP 调用：127 + 358 = {}；事实验收通过", result.result)


if __name__ == "__main__":
    asyncio.run(main())
