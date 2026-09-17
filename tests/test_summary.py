"""验证摘要来源、请求组合与信息损失边界。"""

import unittest
from unittest.mock import MagicMock

from test_tool_call import response
from hello_agent.schemas.context import ContextPolicy
from hello_agent.sdk.e02_context.agent import example_history
from hello_agent.tools.summary import summary_messages


class SummaryTests(unittest.TestCase):
    def test_only_old_history_is_summarized_and_original_is_unchanged(self):
        history = example_history()
        before = history.model_dump()
        client = MagicMock()
        client.chat.completions.create.return_value = response("用户最喜欢青绿色。")
        messages = summary_messages(client, history, "独立问题", "系统", ContextPolicy(mode="window"))
        source = client.chat.completions.create.call_args.kwargs["messages"]
        self.assertIn("青绿色", source[1]["content"])
        self.assertNotIn("hello", source[1]["content"])
        self.assertNotIn("独立问题", str(source))
        self.assertEqual(messages[2:-1], before["messages"][-4:])
        self.assertEqual(messages[1]["role"], "user")
        self.assertNotIn("2 加 3", str(messages))
        self.assertEqual(history.model_dump(), before)

    def test_no_old_history_skips_request(self):
        client = MagicMock()
        messages = summary_messages(client, example_history(), "问题", "系统", ContextPolicy(mode="window", recent_turns=100))
        client.chat.completions.create.assert_not_called()
        self.assertEqual(len(messages), 10)

    def test_zero_window_summarizes_everything(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response("摘要")
        messages = summary_messages(client, example_history(), "问题", "系统", ContextPolicy(mode="window", recent_turns=0))
        self.assertEqual(len(messages), 3)
        self.assertIn("整理书桌", str(client.chat.completions.create.call_args))

    def test_omission_and_distortion_are_not_repaired_from_original(self):
        for summary in ("用户练习了加法。", "用户最喜欢红色。"):
            client = MagicMock()
            client.chat.completions.create.return_value = response(summary)
            messages = summary_messages(client, example_history(), "问题", "系统", ContextPolicy(mode="window"))
            self.assertNotIn("青绿色", str(messages))
            self.assertIn(summary, messages[1]["content"])

    def test_empty_summary_fails_without_mutating_history(self):
        history = example_history()
        before = history.model_dump()
        client = MagicMock()
        client.chat.completions.create.return_value = response("")
        with self.assertRaises(ValueError):
            summary_messages(client, history, "问题", "系统", ContextPolicy(mode="window"))
        self.assertEqual(client.chat.completions.create.call_count, 1)
        self.assertEqual(history.model_dump(), before)
