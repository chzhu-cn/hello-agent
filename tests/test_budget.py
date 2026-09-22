"""验证预算边界、完整轮次和服务输出限制。"""

import unittest
from unittest.mock import MagicMock

from test_tool_call import response
from hello_agent.schemas.config import BudgetConfig
from hello_agent.schemas.context import ContextPolicy
from hello_agent.sdk.e02_context.agent import example_history
from hello_agent.tools.budget import budget_messages, estimate_tokens
from hello_agent.tools.context import build_messages
from hello_agent.tools.llm import request_text


class BudgetTests(unittest.TestCase):
    def budget(self, limit):
        return BudgetConfig(
            context_tokens=limit + 15, output_tokens=10, safety_tokens=5, _env_file=None
        )

    def test_exact_boundary_and_whole_turn_removal(self):
        history = example_history()
        before = history.model_dump()
        full = build_messages(history, "问题", "系统", ContextPolicy(mode="full"))
        exact = estimate_tokens(full)
        self.assertEqual(
            budget_messages(history, "问题", "系统", self.budget(exact)), full
        )
        cut = budget_messages(history, "问题", "系统", self.budget(exact - 1))
        self.assertEqual(cut, [full[0], *full[3:]])
        self.assertLessEqual(estimate_tokens(cut), exact - 1)
        self.assertEqual(history.model_dump(), before)

    def test_only_fixed_messages_and_overflow(self):
        history = example_history()
        full = build_messages(history, "问题", "系统", ContextPolicy(mode="full"))
        fixed = [full[0], full[-1]]
        limit = estimate_tokens(fixed)
        self.assertEqual(
            budget_messages(history, "问题", "系统", self.budget(limit)), fixed
        )
        with self.assertRaises(ValueError):
            budget_messages(history, "问题", "系统", self.budget(limit - 1))

    def test_invalid_config(self):
        for fields in (
            {"context_tokens": 192},
            {"output_tokens": 0},
            {"safety_tokens": -1},
            {"context_tokens": 1},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                BudgetConfig(_env_file=None, **fields)

    def test_multibyte_input_uses_bytes_not_characters(self):
        ascii_count = estimate_tokens([{"role": "user", "content": "a"}])
        chinese_count = estimate_tokens([{"role": "user", "content": "红"}])
        self.assertGreater(chinese_count, ascii_count)

    def test_output_limit_is_sent_and_default_is_unchanged(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response("回复")
        request_text(client, [], max_tokens=128)
        self.assertEqual(
            client.chat.completions.create.call_args.kwargs["max_tokens"], 128
        )
        request_text(client, [])
        self.assertNotIn("max_tokens", client.chat.completions.create.call_args.kwargs)

    def test_truncated_output_is_not_accepted_as_complete(self):
        client = MagicMock()
        truncated = response("半句")
        truncated.choices[0].finish_reason = "length"
        client.chat.completions.create.return_value = truncated
        with self.assertRaises(ValueError):
            request_text(client, [], max_tokens=1)
        self.assertEqual(client.chat.completions.create.call_count, 1)
