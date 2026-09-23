"""真实 stdio 子进程测试，无需模型或 API 密钥。"""

import sys
import unittest
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError
from mcp.types import CONNECTION_CLOSED


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_execution_failure_returns_error_and_session_survives(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).parent / "fixtures" / "mcp_fault_server.py"), "raise"],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=10)
            ) as session:
                await session.initialize()
                await session.list_tools()
                failed = await session.call_tool("add", {"a": 2, "b": 3})
                self.assertTrue(failed.isError)
                self.assertIsNone(failed.structuredContent)
                self.assertTrue(any(
                    item.type == "text" and "injected add execution failure" in item.text
                    for item in failed.content
                ))
                recovered = await session.call_tool("add", {"a": 2, "b": 3})
                self.assertFalse(recovered.isError)
                self.assertEqual(recovered.structuredContent, {"result": 5.0})

    async def test_server_exit_during_call_raises_connection_error(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).parent / "fixtures" / "mcp_fault_server.py"), "disconnect"],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=10)
            ) as session:
                await session.initialize()
                await session.list_tools()
                with self.assertRaises(McpError) as caught:
                    await session.call_tool("add", {"a": 2, "b": 3})
                self.assertEqual(caught.exception.error.code, CONNECTION_CLOSED)
                self.assertEqual(caught.exception.error.message, "Connection closed")

    async def test_discovery_calls_and_errors(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "hello_agent.sdk.e05_mcp.server"],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=10)
            ) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                self.assertEqual([tool.name for tool in tools], ["add"])
                self.assertEqual(set(tools[0].inputSchema["required"]), {"a", "b"})
                result = await session.call_tool("add", {"a": 127, "b": 358})
                self.assertFalse(result.isError)
                self.assertEqual(result.structuredContent, {"result": 485.0})
                for name, args in (
                    ("unknown", {}),
                    ("add", {"a": "bad", "b": 1}),
                    ("add", {"a": 1}),
                    ("add", {"a": 1, "b": 2, "extra": 3}),
                    ("add", {"a": 1e101, "b": 2}),
                ):
                    with self.subTest(name=name, args=args):
                        failed = await session.call_tool(name, args)
                        self.assertTrue(failed.isError)
                recovered = await session.call_tool("add", {"a": 2, "b": 3})
                self.assertFalse(recovered.isError)
                self.assertEqual(recovered.structuredContent, {"result": 5.0})
