"""单进程审批门：只有批准当前提案后，才能写入内存模拟账本。"""

from uuid import UUID

from logly import logger

from hello_agent.schemas.approval import (
    ApprovalState, PaymentArguments, PaymentProposal, PaymentReceipt,
)


class PaymentApproval:
    def __init__(self, payment: PaymentArguments):
        self._state = ApprovalState(proposal=PaymentProposal(payment=payment))
        self._ledger: list[PaymentReceipt] = []

    @property
    def state(self) -> ApprovalState:
        return self._state

    @property
    def ledger(self) -> tuple[PaymentReceipt, ...]:
        return tuple(self._ledger)

    def _check_open(self) -> None:
        if self._state.status in ("rejected", "executed"):
            raise ValueError("本次审批已经结束")

    def _check_proposal(self, proposal_id: UUID) -> None:
        self._check_open()
        if proposal_id != self._state.proposal.id:
            raise ValueError("提案已更新，请查看新参数后重新确认")

    def revise(self, payment: PaymentArguments) -> None:
        self._check_open()
        # 每次修改都生成新提案，旧批准不能沿用。
        self._state = ApprovalState(proposal=PaymentProposal(payment=payment))
        logger.info("提案已修改，批准已清除；新提案 ID：{}", self._state.proposal.id)

    def approve(self, proposal_id: UUID) -> None:
        self._check_proposal(proposal_id)
        self._state = ApprovalState(
            proposal=self._state.proposal, status="approved", approved_id=proposal_id,
        )
        logger.info("已批准提案：{}；尚未记账", proposal_id)

    def reject(self, proposal_id: UUID) -> None:
        self._check_proposal(proposal_id)
        self._state = ApprovalState(proposal=self._state.proposal, status="rejected")
        logger.info("已拒绝提案：{}；未记账", proposal_id)

    def execute(self) -> PaymentReceipt:
        self._check_open()
        state = self._state
        if state.status != "approved" or state.approved_id != state.proposal.id:
            raise ValueError("当前提案尚未批准，禁止记账")
        receipt = PaymentReceipt(
            proposal_id=state.proposal.id, payment=state.proposal.payment,
        )
        self._ledger.append(receipt)
        self._state = ApprovalState(
            proposal=state.proposal, status="executed", approved_id=state.approved_id,
        )
        logger.success("模拟记账完成；提案 ID：{}；账本笔数：{}", receipt.proposal_id, len(self._ledger))
        return receipt
