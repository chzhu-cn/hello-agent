"""评估器不将运行完成当作答对，错误题不阻断后续。"""

import unittest
from unittest.mock import MagicMock

from test_tool_call import response
from hello_agent.sdk.e03_evaluation.agent import cases, evaluate, grade


class EvaluationTests(unittest.TestCase):
    def test_grade_does_not_accept_keyword_match(self):
        self.assertTrue(grade(" 青绿色。 ", "青绿色"))
        for answer in ("不是青绿色", "青绿色或红色", "我不知道是不是青绿色", ""):
            self.assertFalse(grade(answer, "青绿色"))

    def test_completed_wrong_and_failed_are_distinct(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response("红色"), response(""), response("不知道")]
        results = evaluate(client, cases()[:3])
        self.assertEqual([(r.completed, r.passed) for r in results], [(True, False), (False, False), (True, True)])
        self.assertEqual(results[1].error, "ValueError")
        self.assertEqual(client.chat.completions.create.call_count, 3)

    def test_cases_are_independent_and_expected_is_not_sent(self):
        client = MagicMock()
        items = cases()
        before = [item.model_dump() for item in items]
        client.chat.completions.create.side_effect = [response(item.expected) for item in items]
        results = evaluate(client, items)
        self.assertTrue(all(result.passed for result in results))
        self.assertEqual(before, [item.model_dump() for item in items])
        request = client.chat.completions.create.call_args_list[2].kwargs["messages"]
        self.assertEqual(len(request), 2)
        self.assertNotIn("青绿色", str(request))
        self.assertEqual(sum(result.requests for result in results), 6)
