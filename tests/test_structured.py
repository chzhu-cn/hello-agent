"""结构化输出的失败边界及结构正确但事实错误。"""

import unittest

from test_tool_call import response
from hello_agent.sdk.e04_structured.agent import validate_response


class StructuredTests(unittest.TestCase):
    def test_valid_and_unknown(self):
        self.assertEqual(validate_response(response('{"favorite_color":"青绿色"}')).favorite_color, "青绿色")
        self.assertIsNone(validate_response(response('{"favorite_color":null}')).favorite_color)

    def test_invalid_json_fields_and_wrapping(self):
        for text in ('broken', '{}', '{"favorite_color":3}', '{"favorite_color":"红色","extra":1}', '```json\n{"favorite_color":"红色"}\n```', ''):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_response(response(text))

    def test_refusal_truncation_and_missing_choices(self):
        refused = response('{"favorite_color":"青绿色"}')
        refused.choices[0].message.refusal = "拒绝"
        truncated = response('{"favorite_color":"青绿色"}')
        truncated.choices[0].finish_reason = "length"
        empty = response("内容")
        empty.choices = []
        for item in (refused, truncated, empty):
            with self.assertRaises(ValueError):
                validate_response(item)

    def test_wrong_fact_can_pass_schema(self):
        result = validate_response(response('{"favorite_color":"红色"}'))
        self.assertNotEqual(result.favorite_color, "青绿色")
