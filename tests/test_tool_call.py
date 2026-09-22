"""离线验证工具协议与执行边界，不读取真实认证配置。"""

import os
import unittest
from unittest.mock import MagicMock, patch

# 模块级配置实例沿用项目约定，测试覆盖所有配置项。
os.environ.update(
    LLM_MODEL="test-model",
    LLM_API_KEY="test-only",
    LLM_BASE_URL="https://example.com/v1",
    LLM_TIMEOUT="30",
)

from openai.types.chat import ChatCompletion
from pydantic import ValidationError
from hello_agent.sdk.p00_basics.tool_call import run


def response(content=None, calls=None):
    return ChatCompletion(
        id="test",
        object="chat.completion",
        created=0,
        model="test-model",
        choices=[
            {
                "index": 0,
                "finish_reason": "tool_calls" if calls else "stop",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": calls,
                },
            }
        ],
    )


def call(name="add", arguments='{"a":127,"b":358}', id="call_1"):
    return {
        "id": id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


class ToolCallTests(unittest.TestCase):
    def test_round_trip(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            response(calls=[call()]),
            response("485"),
        ]
        self.assertEqual(run(client, "计算"), "485")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["messages"][1]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(
            request["messages"][2],
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": '{"result":485.0}',
            },
        )
        self.assertEqual(request["tool_choice"], "none")
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_direct_answer(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response("你好")
        self.assertEqual(run(client, "你好"), "你好")
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_invalid_calls_never_execute(self):
        for calls in (
            [call(name="unknown")],
            [call(arguments='{"a":"1","b":2}')],
            [call(arguments="not json")],
            [call(arguments='{"a":true,"b":2}')],
            [call(arguments='{"a":1,"b":2,"extra":3}')],
            [call(arguments='{"a":1e200,"b":2}')],
            [call(), call(id="call_2")],
        ):
            with (
                self.subTest(calls=calls),
                patch("hello_agent.sdk.p00_basics.tool_call.add") as add,
            ):
                client = MagicMock()
                client.chat.completions.create.return_value = response(calls=calls)
                with self.assertRaises((ValueError, ValidationError)):
                    run(client, "计算")
                add.assert_not_called()
                self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_no_third_request(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            response(calls=[call()]),
            response(calls=[call()]),
        ]
        with self.assertRaises(ValueError):
            run(client, "计算")
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_empty_answer(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response(" ")
        with self.assertRaises(ValueError):
            run(client, "你好")
