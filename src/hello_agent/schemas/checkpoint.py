"""E09-A：显式保存关键字段，缺失时不能用默认值生成新身份。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from hello_agent.schemas.approval import ApprovalState, PaymentProposal
from hello_agent.schemas.ledger import PaymentOperation


class SavedProposal(PaymentProposal):
    id: UUID


class SavedApproval(ApprovalState):
    proposal: SavedProposal
    status: Literal["pending", "approved", "rejected"]
    approved_id: UUID | None


class ApprovalCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    state: SavedApproval


class ExecutionCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    proposal: SavedProposal
    approved_id: UUID
    phase: Literal["approved", "executing", "succeeded", "unknown", "rejected"]
    result: PaymentOperation | None
    reason: str

    @property
    def operation(self) -> PaymentOperation:
        return PaymentOperation(operation_id=self.proposal.id, payment=self.proposal.payment)

    @model_validator(mode="after")
    def check_consistency(self) -> "ExecutionCheckpoint":
        if self.approved_id != self.proposal.id:
            raise ValueError("执行检查点的批准必须绑定当前提案")
        if self.phase == "succeeded":
            if self.result != self.operation:
                raise ValueError("成功结果必须匹配操作 ID 与参数")
        elif self.result is not None:
            raise ValueError("未确认成功的阶段不能携带成功结果")
        return self
