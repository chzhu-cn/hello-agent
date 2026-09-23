"""读取已登记的本地技能；不执行说明或脚本。"""

from pathlib import Path

from logly import logger

from hello_agent.schemas.skills import LoadedSkill, SkillCatalog, SkillEntry, SkillSummary


class SkillStore:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        catalog_path = self._inside(self.root, "catalog.json")
        self.catalog = SkillCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
        for name, entry in self.catalog.skills.items():
            if name != entry.name:
                raise ValueError("技能清单的键与名称不一致")

    @staticmethod
    def _inside(root: Path, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or path.drive or ".." in path.parts:
            raise ValueError("不允许绝对路径或父目录跳转")
        resolved = (root / path).resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError("文件实际路径越出允许目录")
        return resolved

    def _entry(self, name: str) -> SkillEntry:
        if name not in self.catalog.skills:
            raise ValueError(f"未知技能：{name}")
        return self.catalog.skills[name]

    def discover(self) -> list[SkillSummary]:
        return [
            SkillSummary(name=entry.name, description=entry.description)
            for entry in self.catalog.skills.values()
        ]

    def load(self, name: str) -> LoadedSkill:
        entry = self._entry(name)
        directory = self._inside(self.root, entry.name)
        path = self._inside(directory, "SKILL.md")
        text = path.read_text(encoding="utf-8")
        logger.info("加载技能说明：{}；文件：{}", name, path)
        return LoadedSkill(
            name=name, instructions=text, available_resources=list(entry.resources),
        )

    def load_resource(self, name: str, resource: str) -> str:
        entry = self._entry(name)
        if resource not in entry.resources:
            raise ValueError(f"未知技能资源：{name}/{resource}")
        directory = self._inside(self.root, entry.name)
        path = self._inside(directory, entry.resources[resource])
        text = path.read_text(encoding="utf-8")
        logger.info("加载技能资源：{}/{}；文件：{}", name, resource, path)
        return text
