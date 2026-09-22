"""响应包装清理不改变 JSON 内容或掩盖不完整响应。"""

import unittest

from unittest.mock import MagicMock

from test_tool_call import response
from hello_agent.tools.llm import request_text


class TextTests(unittest.TestCase):
    def clean(self, text):
        client = MagicMock()
        client.chat.completions.create.return_value = response(text)
        return request_text(client, [])

    def test_multiple_leading_think_blocks(self):
        self.assertEqual(
            self.clean(" <think>a</think>\n<think>b</think> 正文 "), "正文"
        )

    def test_missing_body_or_unclosed_think(self):
        for text in ("<think>未闭合", "<think>只有思考</think>"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.clean(text)

    def test_literal_tags_in_json_preserved(self):
        text = '{"issues":["保留 <think>字面量</think> 和 ```json"]}'
        self.assertEqual(self.clean(text), text)

    def test_no_guessing_between_multiple_objects(self):
        text = "说明 ```json\n{}\n``` 然后 {}"
        self.assertEqual(self.clean(text), text)

    def test_public_request_removes_json_wrapper(self):
        self.assertEqual(
            self.clean('<think>检查</think>```json\n{"passed":true,"issues":[]}\n```'),
            '{"passed":true,"issues":[]}',
        )

    def test_empty_json_fence_is_empty_response(self):
        with self.assertRaisesRegex(ValueError, "空文本"):
            self.clean("```json\n\n```")
