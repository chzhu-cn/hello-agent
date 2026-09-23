"""stdio 服务端：标准输出留给 MCP 协议，不加载模型配置。"""

import asyncio
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from hello_agent.schemas.mcp_tools import MCP_ADD_TOOL
from hello_agent.schemas.tools import AddArguments, AddResult
from hello_agent.tools.arithmetic import add


server = Server("hello-agent-add")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [MCP_ADD_TOOL]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name != "add":
        raise ValueError(f"未知工具：{name}")
    args = AddArguments.model_validate(arguments)
    return AddResult(result=add(args.a, args.b)).model_dump()


async def main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
