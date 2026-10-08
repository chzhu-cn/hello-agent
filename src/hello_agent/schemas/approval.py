"""E07：模拟付款参数、审批快照与账本记录。"""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaymentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    recipient: str = Field(min_length=1, max_length=80)
    amount_cents: int = Field(strict=True, gt=0, le=100_000_000)
    currency: Literal["CNY"] = "CNY"
    note: str = Field(min_length=1, max_length=200)


class PaymentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    payment: PaymentArguments


class PaymentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payment: PaymentArguments | None
    reason: str = Field(min_length=1, max_length=500)


class ApprovalState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal: PaymentProposal
    status: Literal["pending", "approved", "rejected", "executed"] = "pending"
    approved_id: UUID | None = None

    @model_validator(mode="after")
    def approval_matches_proposal(self) -> "ApprovalState":
        if self.status in ("approved", "executed"):
            if self.approved_id != self.proposal.id:
                raise ValueError("批准记录必须匹配当前提案 ID")
        elif self.approved_id is not None:
            raise ValueError("待审批或拒绝状态不能携带批准记录")
        return self


class PaymentReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: UUID
    payment: PaymentArguments
