"""E07：模拟付款参数、审批快照与账本记录。"""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


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


class PaymentReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: UUID
    payment: PaymentArguments
