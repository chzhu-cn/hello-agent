"""验证会话历史的传递、隔离与失败边界。"""

from copy import deepcopy
import unittest
from unittest.mock import MagicMock

from test_tool_call import response
from hello_agent.schemas.memory import Conversation
from hello_agent.sdk.e01_memory.agent import chat


class MemoryTests(unittest.TestCase):
    def test_history_and_isolation(self):
        client = MagicMock()
        snapshots = []
        replies = iter([response("记住了"), response("青绿色"), response("不知道")])

        def request(**kwargs):
            snapshots.append(deepcopy(kwargs["messages"]))
            return next(replies)

        client.chat.completions.create.side_effect = request
        first, second = Conversation(), Conversation()
        chat(client, first, "喜欢青绿色")
        chat(client, first, "喜欢什么颜色？")
        chat(client, second, "喜欢什么颜色？")
        self.assertEqual(
            [m["role"] for m in snapshots[1]], ["system", "user", "assistant", "user"]
        )
        self.assertEqual(snapshots[1][1]["content"], "喜欢青绿色")
        self.assertEqual(snapshots[1][2]["content"], "记住了")
        self.assertEqual(len(snapshots[2]), 2)
        self.assertEqual(len(first.messages), 4)
        self.assertEqual(len(second.messages), 2)

    def test_failure_preserves_completed_turns(self):
        for failure in (RuntimeError("connection"), response("")):
            with self.subTest(failure=failure):
                client = MagicMock()
                client.chat.completions.create.side_effect = [
                    response("收到"),
                    failure,
                    response("恢复"),
                ]
                session = Conversation()
                chat(client, session, "第一轮")
                before = session.model_dump()
                with self.assertRaises((RuntimeError, ValueError)):
                    chat(client, session, "失败轮")
                self.assertEqual(session.model_dump(), before)
                chat(client, session, "下一轮")
                sent = client.chat.completions.create.call_args.kwargs["messages"]
                self.assertNotIn("失败轮", [m["content"] for m in sent])
                self.assertEqual(client.chat.completions.create.call_count, 3)

    def test_blank_input_does_not_request(self):
        client = MagicMock()
        session = Conversation()
        with self.assertRaises(ValueError):
            chat(client, session, "  ")
        client.chat.completions.create.assert_not_called()
        self.assertEqual(session.messages, [])
