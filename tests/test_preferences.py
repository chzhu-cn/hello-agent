"""验证明确偏好的存储、更新、删除及实际请求边界。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from test_tool_call import response
from hello_agent.sdk.e01_memory.preferences import ask
from hello_agent.tools.preferences import (
    load_preferences,
    preference_path,
    update_preference,
)


class PreferenceTests(unittest.TestCase):
    def test_update_delete_and_request_context(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            client = MagicMock()
            client.chat.completions.create.return_value = response("受控回复")
            for value in ("青绿色", "紫色", None):
                update_preference(directory, "a", "颜色", value)
                loaded = load_preferences(directory, "a")
                expected = {"颜色": value} if value else {}
                self.assertEqual(loaded.values, expected)
                ask(client, loaded, "喜欢什么颜色？")
                sent = client.chat.completions.create.call_args.kwargs["messages"]
                self.assertEqual(len(sent), 3)
                self.assertEqual(sent[1]["content"], loaded.model_dump_json())
                if value != "青绿色":
                    self.assertNotIn("青绿色", str(sent))
                if value is None:
                    self.assertNotIn("紫色", str(sent))
            update_preference(directory, "a", "颜色", None)
            self.assertEqual(load_preferences(directory, "a").values, {})
            self.assertEqual(load_preferences(directory, "b").values, {})

    def test_invalid_changes_preserve_file(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            update_preference(directory, "a", "颜色", "青绿色")
            for key, value in ((" ", "值"), ("颜色", " "), ("颜色", "x" * 501)):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    update_preference(directory, "a", key, value)
            self.assertEqual(
                load_preferences(directory, "a").values, {"颜色": "青绿色"}
            )
            with self.assertRaises(ValueError):
                load_preferences(directory, "../outside")

    def test_corruption_is_not_overwritten(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            path = preference_path(directory, "a")
            for content in ("broken", '{"values":{"颜色":42}}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    update_preference(directory, "a", "颜色", "紫色")
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_failed_save_preserves_previous_preferences(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            update_preference(directory, "a", "颜色", "青绿色")
            for value in ("紫色", None):
                with patch("pathlib.Path.replace", side_effect=OSError("disk")):
                    with self.assertRaises(OSError):
                        update_preference(directory, "a", "颜色", value)
                self.assertEqual(
                    load_preferences(directory, "a").values, {"颜色": "青绿色"}
                )
                self.assertEqual(
                    list(directory.iterdir()), [preference_path(directory, "a")]
                )
