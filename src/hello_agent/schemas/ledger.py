"""持久模拟记账的操作标识与参数。"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from hello_agent.schemas.approval import PaymentArguments


class PaymentOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: UUID
    payment: PaymentArguments
