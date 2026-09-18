"""工具历史必须整轮裁剪，非法配对不可静默丢弃。"""

import unittest

from test_tool_call import response  # 初始化离线配置
from hello_agent.schemas.config import BudgetConfig
from hello_agent.schemas.tool_history import ToolHistory
from hello_agent.sdk.e02_context.tool_budget import example_history
from hello_agent.tools.tool_context import budget_tool_history, estimate_tool_tokens


class ToolContextTests(unittest.TestCase):
    def config(self, limit):
        return BudgetConfig(context_tokens=limit + 15, output_tokens=10, safety_tokens=5, _env_file=None)

    def test_exact_budget_and_whole_turn_removal(self):
        history = example_history()
        before = history.model_dump()
        full = budget_tool_history(history, "问题", "系统", self.config(10000))
        limit = estimate_tool_tokens(full)
        self.assertEqual(budget_tool_history(history, "问题", "系统", self.config(limit)), full)
        trimmed = budget_tool_history(history, "问题", "系统", self.config(limit - 1))
        self.assertEqual([m["role"] for m in trimmed], ["system", "user", "assistant", "user"])
        self.assertNotIn("add_1", str(trimmed))
        self.assertNotIn("结果分别", str(trimmed))
        self.assertEqual(history.model_dump(), before)

    def test_missing_duplicate_and_unknown_results(self):
        for kind in ("missing", "duplicate", "unknown", "duplicate_call"):
            data = example_history().model_dump()
            exchange = data["turns"][0]["exchanges"][0]
            if kind == "missing":
                exchange["results"].pop()
            elif kind == "duplicate":
                exchange["results"].append(exchange["results"][0])
            elif kind == "unknown":
                exchange["results"][0]["tool_call_id"] = "unknown"
            else:
                exchange["calls"][1]["id"] = "add_1"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                ToolHistory.model_validate(data)

    def test_result_order_is_matched_by_id(self):
        data = example_history().model_dump()
        data["turns"][0]["exchanges"][0]["results"].reverse()
        history = ToolHistory.model_validate(data)
        messages = budget_tool_history(history, "问题", "系统", self.config(10000))
        self.assertEqual([m["tool_call_id"] for m in messages if m["role"] == "tool"], ["add_2", "add_1"])

    def test_mutated_incomplete_history_rejected_even_under_tiny_budget(self):
        history = example_history()
        history.turns[0].exchanges[0].results.pop()
        with self.assertRaises(ValueError):
            budget_tool_history(history, "问题", "系统", self.config(1))

    def test_arguments_and_results_are_counted(self):
        history = example_history()
        full = budget_tool_history(history, "问题", "系统", self.config(10000))
        history.turns[0].exchanges[0].calls[0].function.arguments += " " * 100
        larger = budget_tool_history(history, "问题", "系统", self.config(10000))
        self.assertEqual(estimate_tool_tokens(larger) - estimate_tool_tokens(full), 100)

    def test_fixed_messages_overflow_and_empty_history(self):
        history = ToolHistory()
        messages = budget_tool_history(history, "问题", "系统", self.config(1000))
        self.assertEqual(len(messages), 2)
        with self.assertRaises(ValueError):
            budget_tool_history(history, "问题", "系统", self.config(estimate_tool_tokens(messages) - 1))
