"""
固定本地示例：先发现，再按命令行选择加载，不调用模型。

# 只查看技能名称与用途
uv run python -m hello_agent.sdk.e06_skill.local

# 加载加法指导及示例资源
uv run python -m hello_agent.sdk.e06_skill.local addition-guide --resource example
"""

import argparse
from pathlib import Path

from logly import logger

from hello_agent.tools.skills import SkillStore


def main() -> None:
    parser = argparse.ArgumentParser(description="发现与按需加载本地技能")
    parser.add_argument("skill", nargs="?", help="省略时仅展示名称与用途")
    parser.add_argument("--resource", help="选中技能内登记的资源名称")
    args = parser.parse_args()
    if args.resource and not args.skill:
        parser.error("读取资源前需要指定技能名称")
    try:
        store = SkillStore(Path(__file__).parent / "skills")
        for skill in store.discover():
            logger.info("发现技能：{}；用途：{}", skill.name, skill.description)
        if args.skill:
            loaded = store.load(args.skill)
            logger.info("技能正文：\n{}", loaded.instructions)
            for resource in loaded.available_resources:
                logger.info("可按需读取的资源：{}", resource)
            if args.resource:
                logger.info("资源正文：\n{}", store.load_resource(args.skill, args.resource))
    except (ValueError, OSError) as exc:
        logger.error("技能加载失败：{}", exc)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
