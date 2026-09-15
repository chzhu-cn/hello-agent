"""验证磁盘历史、跨进程恢复和保存失败边界。"""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from test_tool_call import response
from hello_agent.schemas.memory import Conversation, ConversationMessage
from hello_agent.sdk.e01_memory.agent import persistent_chat
from hello_agent.tools.memory import load_session, save_session, session_path


class MemoryStorageTests(unittest.TestCase):
    def history(self):
        return Conversation(messages=[
            ConversationMessage(role="user", content="喜欢青绿色"),
            ConversationMessage(role="assistant", content="收到"),
        ])

    def test_roundtrip_and_isolation(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            save_session(directory, "a", self.history())
            self.assertEqual(load_session(directory, "a"), self.history())
            self.assertEqual(load_session(directory, "b").messages, [])

    def test_restore_in_new_process(self):
        with TemporaryDirectory() as folder:
            save_session(Path(folder), "a", self.history())
            script = (
                "import sys; from pathlib import Path; "
                "from hello_agent.tools.memory import load_session; "
                "s = load_session(Path(sys.argv[1]), 'a'); "
                "assert len(s.messages) == 2; "
                "assert s.messages[0].content == '\u559c\u6b22\u9752\u7eff\u8272'"
            )
            result = subprocess.run(
                [sys.executable, "-c", script, folder],
                capture_output=True, text=True, env=os.environ.copy(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_file_is_not_overwritten(self):
        for content in ('broken', '{"messages":[{"role":"user","content":"unfinished"}]}'):
            with self.subTest(content=content), TemporaryDirectory() as folder:
                directory = Path(folder)
                path = session_path(directory, "a")
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_session(directory, "a")
                self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_invalid_names(self):
        for name in ("../escape", "a/b", "a\\b", "", "a" * 65):
            with self.subTest(name=name), self.assertRaises(ValueError):
                session_path(Path("unused"), name)

    def test_failed_replace_preserves_file_and_cleans_temporary(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            save_session(directory, "a", self.history())
            with patch("pathlib.Path.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    save_session(directory, "a", Conversation())
            self.assertEqual(load_session(directory, "a"), self.history())
            self.assertEqual(list(directory.iterdir()), [session_path(directory, "a")])

    def test_persistent_turn_commit_and_failures(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            session = self.history()
            client = MagicMock()
            client.chat.completions.create.return_value = response("青绿色")
            with patch("hello_agent.sdk.e01_memory.agent.memory_config") as config:
                config.directory = directory
                updated = persistent_chat(client, session, "喜欢什么颜色？", "a")
                self.assertEqual(len(session.messages), 2)
                self.assertEqual(len(updated.messages), 4)
                self.assertEqual(load_session(directory, "a"), updated)
                with patch("hello_agent.sdk.e01_memory.agent.save_session", side_effect=OSError("disk")):
                    with self.assertRaises(OSError):
                        persistent_chat(client, updated, "下一轮", "a")
                self.assertEqual(len(updated.messages), 4)
                client.chat.completions.create.return_value = response("")
                with self.assertRaises(ValueError):
                    persistent_chat(client, updated, "失败轮", "a")
                self.assertEqual(load_session(directory, "a"), updated)
