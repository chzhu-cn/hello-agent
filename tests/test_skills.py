"""技能发现、按需读取与路径边界验证。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hello_agent.tools.skills import SkillStore


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "skills"
        self.root.mkdir()
        self.catalog = {"skills": {
            name: {"name": name, "description": name, "resources": {"example": "example.md"}}
            for name in ("first", "second")
        }}
        for name in self.catalog["skills"]:
            directory = self.root / name
            directory.mkdir()
            (directory / "SKILL.md").write_text(f"{name} instructions", encoding="utf-8")
            (directory / "example.md").write_text(f"{name} example", encoding="utf-8")
        self.write_catalog()

    def write_catalog(self):
        (self.root / "catalog.json").write_text(json.dumps(self.catalog), encoding="utf-8")

    def test_discovery_and_loading_read_only_requested_files(self):
        reads = []
        original = Path.read_text

        def tracked(path, *args, **kwargs):
            reads.append(path.relative_to(self.root).as_posix())
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", tracked):
            store = SkillStore(self.root)
            self.assertEqual([item.name for item in store.discover()], ["first", "second"])
            self.assertEqual(reads, ["catalog.json"])
            loaded = store.load("first")
            self.assertEqual(loaded.instructions, "first instructions")
            self.assertEqual(loaded.available_resources, ["example"])
            self.assertEqual(reads, ["catalog.json", "first/SKILL.md"])
            self.assertEqual(store.load_resource("first", "example"), "first example")
            self.assertEqual(reads, ["catalog.json", "first/SKILL.md", "first/example.md"])

    def test_unknown_names_are_rejected_without_reading(self):
        store = SkillStore(self.root)
        with patch.object(Path, "read_text", side_effect=AssertionError("不应读取文件")):
            for name in ("unknown", "../first", str(self.root / "first")):
                with self.assertRaises(ValueError):
                    store.load(name)
            with self.assertRaises(ValueError):
                store.load_resource("first", "../example.md")

    def test_registered_paths_cannot_escape_skill_directory(self):
        for resource_path in ("../second/example.md", str(self.root / "second" / "example.md")):
            with self.subTest(path=resource_path):
                self.catalog["skills"]["first"]["resources"]["example"] = resource_path
                self.write_catalog()
                store = SkillStore(self.root)
                with self.assertRaises(ValueError):
                    store.load_resource("first", "example")

    def test_missing_resource_does_not_prevent_discovery_or_instruction_loading(self):
        (self.root / "first" / "example.md").unlink()
        store = SkillStore(self.root)
        self.assertEqual(len(store.discover()), 2)
        self.assertEqual(store.load("first").instructions, "first instructions")
        with self.assertRaises(FileNotFoundError):
            store.load_resource("first", "example")

    def test_symlink_to_outside_is_rejected(self):
        outside = self.base / "outside.md"
        outside.write_text("outside", encoding="utf-8")
        link = self.root / "first" / "link.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"当前环境无法创建符号链接：{exc}")
        self.catalog["skills"]["first"]["resources"]["example"] = "link.md"
        self.write_catalog()
        with self.assertRaises(ValueError):
            SkillStore(self.root).load_resource("first", "example")
