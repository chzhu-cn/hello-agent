"""受控模型响应验证 MCP 适配，不请求真实模型。"""

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from mcp.types import CallToolResult, ListToolsResult, TextContent
from openai.types.chat import ChatCompletion

from hello_agent.schemas.mcp_tools import MCP_ADD_TOOL
from hello_agent.sdk.e05_mcp.agent import run


def response(content=None, name=None, arguments='{"a":127,"b":358}'):
    return ChatCompletion(
        id="test", object="chat.completion", created=0, model="test",
        choices=[{
            "index": 0, "finish_reason": "tool_calls" if name else "stop",
            "message": {
                "role": "assistant", "content": content,
                "tool_calls": [{
                    "id": "mcp_1", "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }] if name else None,
            },
        }],
    )


class MCPAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = MagicMock()
        self.client.chat.completions.create = AsyncMock()
        self.session = AsyncMock()
        self.session.list_tools.return_value = ListToolsResult(tools=[MCP_ADD_TOOL])

    async def test_success_and_error_results_preserve_id(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                self.client.chat.completions.create.side_effect = [
                    response(name="add"), response("工具失败" if failed else "485"),
                ]
                self.session.call_tool.return_value = CallToolResult(
                    isError=failed,
                    content=[TextContent(type="text", text="失败" if failed else "485")],
                    structuredContent=None if failed else {"result": 485.0},
                )
                await run(self.client, self.session, "test", "计算")
                self.session.call_tool.assert_awaited_with("add", {"a": 127, "b": 358})
                request = self.client.chat.completions.create.call_args.kwargs
                self.assertEqual(request["tools"][0]["function"]["parameters"], MCP_ADD_TOOL.inputSchema)
                self.assertEqual(request["messages"][1]["tool_calls"][0]["id"], "mcp_1")
                result = request["messages"][2]
                self.assertEqual(result["tool_call_id"], "mcp_1")
                self.assertEqual(json.loads(result["content"])["isError"], failed)
                self.assertEqual(request["tool_choice"], "none")

    async def test_direct_answer(self):
        self.client.chat.completions.create.return_value = response("你好")
        self.assertEqual(await run(self.client, self.session, "test", "你好"), "你好")
        self.session.call_tool.assert_not_awaited()

    async def test_invalid_calls_do_not_execute(self):
        for name, arguments in (("unknown", "{}"), ("add", "[]"), ("add", "invalid")):
            with self.subTest(name=name, arguments=arguments):
                self.client.chat.completions.create.return_value = response(name=name, arguments=arguments)
                with self.assertRaises(ValueError):
                    await run(self.client, self.session, "test", "计算")
                self.session.call_tool.assert_not_awaited()

    async def test_connection_failure_stops_without_retry(self):
        self.client.chat.completions.create.return_value = response(name="add")
        self.session.call_tool.side_effect = ConnectionError("受控断开")
        with self.assertRaises(ConnectionError):
            await run(self.client, self.session, "test", "计算")
        self.session.call_tool.assert_awaited_once()
        self.client.chat.completions.create.assert_awaited_once()
