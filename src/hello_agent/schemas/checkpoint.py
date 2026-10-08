"""E09-A：显式保存关键字段，缺失时不能用默认值生成新身份。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from hello_agent.schemas.approval import ApprovalState, PaymentProposal


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
