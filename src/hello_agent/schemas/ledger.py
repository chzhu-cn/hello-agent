"""持久模拟记账的操作标识与参数。"""

from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from hello_agent.schemas.approval import PaymentArguments


class PaymentOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    payment: PaymentArguments


ExecutionStatus = Literal["succeeded", "rejected", "unknown"]


class ExecutionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    status: ExecutionStatus
    attempts: int = Field(ge=1)
    queries: int = Field(ge=0)
    reason: str
