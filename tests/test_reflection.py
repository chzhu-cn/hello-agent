"""P3 的事实传递、修改边界与检查误判。"""

import json
import unittest
from unittest.mock import MagicMock, patch

from test_tool_call import response
from hello_agent.sdk.p03_reflection import agent

GOOD = "127 + 358 = 485；485 + 96 = 581；最终结果 581。"
BAD = "485 + 69 = 554，最终结果 554。"
PASS = '{"passed":true,"issues":[]}'
FAIL = '{"passed":false,"issues":["将 69 改为 96，第二步和最终结果改为 581。"]}'


class ReflectionTests(unittest.TestCase):
    def setUp(self):
        setting = patch.object(agent.reflection_config, "max_revisions", 1)
        setting.start()
        self.addCleanup(setting.stop)

    def client(self, *texts):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response(text) for text in texts]
        return client

    def test_first_pass(self):
        result = agent.run(self.client(GOOD, PASS))
        self.assertEqual(
            (result.requests, result.revisions, result.stop_reason), (2, 0, "passed")
        )

    def test_think_and_json_fences(self):
        for feedback in (
            f"```json\n{PASS}\n```",
            f"<think>检查中</think>\n```JSON\n{PASS}\n```",
            f"``json {PASS} ``",
            f"```\n{PASS}\n```",
        ):
            with self.subTest(feedback=feedback):
                result = agent.run(
                    self.client(f"<think>计算中</think>{GOOD}", feedback)
                )
                self.assertEqual(result.answer, GOOD)
                self.assertEqual(result.requests, 2)
                self.assertTrue(result.critique.passed)

    def test_wrapping_does_not_repair_missing_value(self):
        client = self.client(GOOD, '```json {"passed":true,"issues": } ```')
        with self.assertRaisesRegex(ValueError, "检查反馈无效"):
            agent.run(client)

    def test_revision_has_evidence_and_does_not_repeat_tools(self):
        client = self.client(BAD, FAIL, GOOD, PASS)
        with patch.object(agent, "add", wraps=agent.add) as add:
            result = agent.run(client)
        self.assertEqual(add.call_count, 2)
        self.assertEqual(
            (result.answer, result.requests, result.revisions), (GOOD, 4, 1)
        )
        calls = client.chat.completions.create.call_args_list
        for call in calls:
            payload = json.loads(call.kwargs["messages"][-1]["content"])
            self.assertEqual(payload["task"], agent.TASK)
            self.assertEqual(
                [record["result"] for record in payload["records"]], [485, 581]
            )
        revision_payload = json.loads(calls[2].kwargs["messages"][-1]["content"])
        self.assertEqual(revision_payload["answer"], BAD)
        self.assertFalse(revision_payload["critique"]["passed"])
        self.assertEqual(
            json.loads(calls[3].kwargs["messages"][-1]["content"])["answer"], GOOD
        )

    def test_revision_limit(self):
        result = agent.run(self.client(BAD, FAIL, BAD, FAIL))
        self.assertEqual((result.stop_reason, result.requests), ("revision_limit", 4))
        self.assertFalse(result.critique.passed)

    def test_zero_revisions(self):
        with patch.object(agent.reflection_config, "max_revisions", 0):
            result = agent.run(self.client(BAD, FAIL))
        self.assertEqual((result.requests, result.stop_reason), (2, "revision_limit"))

    def test_invalid_feedback_stops(self):
        for feedback in (
            "bad json",
            '{"passed":true,"issues":["错误"]}',
            '{"passed":false,"issues":[]}',
            '{"passed":false,"issues":[" "]}',
        ):
            with self.subTest(feedback=feedback):
                client = self.client(GOOD, feedback)
                with self.assertRaisesRegex(ValueError, "检查反馈无效"):
                    agent.run(client)
                self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_empty_response_stops(self):
        client = self.client("")
        with self.assertRaisesRegex(ValueError, "空文本"):
            agent.run(client)
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_request_failure_no_retry(self):
        client = self.client()
        client.chat.completions.create.side_effect = RuntimeError("request failed")
        with self.assertRaisesRegex(RuntimeError, "request failed"):
            agent.run(client)
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_tool_failure_stops_before_model(self):
        client = self.client()
        with patch.object(
            agent, "add", side_effect=[485, RuntimeError("failure")]
        ) as add:
            with self.assertRaisesRegex(ValueError, "工具执行失败"):
                agent.run(client)
        self.assertEqual(add.call_count, 2)
        client.chat.completions.create.assert_not_called()

    def test_critic_can_wrongly_pass(self):
        result = agent.run(self.client(BAD, PASS))
        self.assertTrue(result.critique.passed)
        self.assertNotEqual(result.answer, GOOD)
        self.assertIn("554", result.answer)
