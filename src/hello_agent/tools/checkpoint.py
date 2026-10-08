"""审批检查点：先写临时文件，再替换目标文件。"""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from logly import logger

from hello_agent.schemas.approval import ApprovalState
from hello_agent.schemas.checkpoint import ApprovalCheckpoint


def save_approval(path: Path, state: ApprovalState) -> None:
    checkpoint = ApprovalCheckpoint.model_validate({"version": 1, "state": state.model_dump()})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(checkpoint.model_dump_json(indent=2))
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    logger.info("已保存审批检查点：{}；状态：{}", path, state.status)


def load_approval(path: Path) -> ApprovalState:
    checkpoint = ApprovalCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
    state = ApprovalState.model_validate(checkpoint.state.model_dump())
    logger.info("已恢复审批检查点：{}；状态：{}", path, state.status)
    return state
