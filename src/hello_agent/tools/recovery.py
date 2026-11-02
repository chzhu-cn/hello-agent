"""执行前记录未决状态；恢复只查询原操作，不盲目重发。"""

from collections.abc import Callable
from pathlib import Path

from logly import logger

from hello_agent.schemas.approval import ApprovalState
from hello_agent.schemas.checkpoint import ExecutionCheckpoint, SavedProposal
from hello_agent.tools.checkpoint import write_checkpoint
from hello_agent.tools.ledger import IdempotencyConflict, PaymentLedger


def load_execution(path: Path) -> ExecutionCheckpoint:
    return ExecutionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))


def save_execution(path: Path, checkpoint: ExecutionCheckpoint) -> None:
    validated = ExecutionCheckpoint.model_validate(checkpoint.model_dump())
    write_checkpoint(path, validated.model_dump_json(indent=2))
    logger.info("已保存执行阶段：{}；操作 ID：{}", validated.phase, validated.proposal.id)


def prepare_execution(path: Path, approval: ApprovalState) -> ExecutionCheckpoint:
    approval = ApprovalState.model_validate(approval.model_dump())
    if approval.status != "approved" or approval.approved_id is None:
        raise ValueError("当前提案未批准，不能准备执行")
    if path.exists():
        existing = load_execution(path)
        if existing.proposal.model_dump() != approval.proposal.model_dump() or existing.approved_id != approval.approved_id:
            raise ValueError("执行检查点属于另一提案，请使用新的检查点路径")
        return existing
    checkpoint = ExecutionCheckpoint(
        version=1, proposal=SavedProposal.model_validate(approval.proposal.model_dump()), approved_id=approval.approved_id,
        phase="approved", result=None, reason="已保存批准，尚未启动工具",
    )
    save_execution(path, checkpoint)
    return checkpoint


def recover_execution(path: Path, ledger: PaymentLedger) -> ExecutionCheckpoint:
    checkpoint = load_execution(path)
    if checkpoint.phase in ("approved", "succeeded", "rejected"):
        return checkpoint
    try:
        found = ledger.query(checkpoint.proposal.id)
    except Exception as exc:
        update = {"phase": "unknown", "reason": f"查询失败：{type(exc).__name__}，保留未决状态"}
    else:
        if found == checkpoint.operation:
            update = {"phase": "succeeded", "result": found, "reason": "恢复查询确认已成功，没有重跑工具"}
        else:
            update = {"phase": "unknown", "reason": "未查到匹配结果，停止自动执行"}
    restored = ExecutionCheckpoint.model_validate(checkpoint.model_dump() | update)
    save_execution(path, restored)
    return restored


def execute_saved(
    path: Path, ledger: PaymentLedger, *, interrupt: Callable[[str], None] | None = None,
) -> ExecutionCheckpoint:
    checkpoint = load_execution(path)
    if checkpoint.phase != "approved":
        return recover_execution(path, ledger)
    pending = ExecutionCheckpoint.model_validate(checkpoint.model_dump() | {
        "phase": "executing", "reason": "准备调用工具，执行结果尚未确认",
    })
    save_execution(path, pending)
    if interrupt:
        interrupt("before-call")
    try:
        result = ledger.execute(pending.operation)
    except IdempotencyConflict:
        completed = ExecutionCheckpoint.model_validate(pending.model_dump() | {
            "phase": "rejected", "reason": "操作 ID 与账本参数冲突，未执行当前请求",
        })
    except Exception:
        return recover_execution(path, ledger)
    else:
        if interrupt:
            interrupt("after-call")
        completed = ExecutionCheckpoint.model_validate(pending.model_dump() | {
            "phase": "succeeded", "result": result, "reason": "工具返回成功，保存执行结果",
        })
    save_execution(path, completed)
    return completed
