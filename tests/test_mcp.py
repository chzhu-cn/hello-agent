"""真实 stdio 子进程测试，无需模型或 API 密钥。"""

import sys
import unittest
from datetime import timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPTests(unittest.IsolatedAsyncioTestCase):
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
