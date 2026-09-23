"""本地技能目录、发现结果与加载结果。"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


SkillName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$", max_length=64)]


class SkillSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: SkillName
    description: str = Field(min_length=1)


class SkillEntry(SkillSummary):
    resources: dict[SkillName, str] = Field(default_factory=dict)


class SkillCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: dict[SkillName, SkillEntry]


class LoadedSkill(BaseModel):
    name: SkillName
    instructions: str
    available_resources: list[str]
