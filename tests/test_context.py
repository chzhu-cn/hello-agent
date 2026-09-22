"""验证上下文裁剪边界与两个请求的独立性。"""

import unittest
from unittest.mock import MagicMock, patch

from test_tool_call import response
from hello_agent.schemas.config import ContextConfig
from hello_agent.schemas.context import ContextPolicy
from hello_agent.schemas.memory import Conversation, ConversationMessage
from hello_agent.sdk.e02_context.agent import compare, example_history
from hello_agent.tools.context import build_messages


class ContextTests(unittest.TestCase):
    def test_full_and_window_keep_complete_turns_without_mutation(self):
        history = example_history()
        before = history.model_dump()
        full = build_messages(history, "问题", "系统", ContextPolicy(mode="full"))
        window = build_messages(
            history, "问题", "系统", ContextPolicy(mode="window", recent_turns=2)
        )
        self.assertEqual(full[1:-1], before["messages"])
        self.assertEqual(window[1:-1], before["messages"][-4:])
        self.assertEqual(window[0], full[0])
        self.assertEqual(window[-1], full[-1])
        self.assertNotIn("青绿色", str(window))
        window[1]["content"] = "修改请求副本"
        self.assertEqual(history.model_dump(), before)

    def test_zero_large_and_empty_windows(self):
        for turns, expected in ((0, 0), (1, 2), (4, 8), (100, 8)):
            messages = build_messages(
                example_history(),
                "问题",
                "系统",
                ContextPolicy(mode="window", recent_turns=turns),
            )
            self.assertEqual(len(messages), expected + 2)
        for mode in ("full", "window"):
            messages = build_messages(
                Conversation(), "问题", "系统", ContextPolicy(mode=mode)
            )
            self.assertEqual([m["role"] for m in messages], ["system", "user"])

    def test_invalid_input_is_rejected(self):
        for turns in (-1, 101):
            with self.assertRaises(ValueError):
                ContextPolicy(mode="window", recent_turns=turns)
            with self.assertRaises(ValueError):
                ContextConfig(recent_turns=turns, _env_file=None)
        history = example_history()
        with self.assertRaises(ValueError):
            build_messages(history, " ", "系统", ContextPolicy(mode="full"))
        history.messages.append(ConversationMessage(role="user", content="半轮"))
        with self.assertRaises(ValueError):
            build_messages(history, "问题", "系统", ContextPolicy(mode="window"))

    def test_comparison_does_not_leak_first_answer(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            response("唯一回答标记"),
            response("不知道"),
        ]
        history = example_history()
        before = history.model_dump()
        with patch("hello_agent.sdk.e02_context.agent.context_config") as config:
            config.recent_turns = 2
            compare(client, history)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(calls[0].kwargs["messages"]), 10)
        self.assertEqual(len(calls[1].kwargs["messages"]), 6)
        self.assertNotIn("唯一回答标记", str(calls[1]))
        self.assertEqual(history.model_dump(), before)

    def test_failure_still_runs_independent_comparison_and_reports_failure(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response(""), response("不知道")]
        with self.assertRaises(SystemExit) as raised:
            compare(client, example_history())
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_preview_does_not_request(self):
        with patch("hello_agent.sdk.e02_context.agent.request_text") as request:
            compare(None, example_history())
        request.assert_not_called()
