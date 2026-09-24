"""本地审批体验：uv run python -m hello_agent.sdk.e07_approval.local"""

from logly import logger

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.tools.approval import PaymentApproval


def run(review: PaymentApproval) -> None:
    while review.state.status not in ("rejected", "executed"):
        proposal = review.state.proposal
        payment = proposal.payment
        logger.info(
            "待审批提案：{}\n收款人：{}\n金额：{}.{:02d} {}\n用途：{}\n当前模拟账本：{} 笔",
            proposal.id, payment.recipient,
            payment.amount_cents // 100, payment.amount_cents % 100,
            payment.currency, payment.note, len(review.ledger),
        )
        logger.info("输入 a 批准并记账，r 拒绝，m 修改；退出或输入结束视为拒绝。")
        try:
            action = input().strip().lower()
            if action == "a":
                review.approve(proposal.id)
                review.execute()
            elif action == "r":
                review.reject(proposal.id)
            elif action == "m":
                logger.info("输入新收款人：")
                recipient = input()
                logger.info("输入新金额，单位分，必须是正整数（12500 表示 125.00 元）：")
                amount_cents = int(input())
                logger.info("输入新用途：")
                note = input()
                review.revise(PaymentArguments(
                    recipient=recipient, amount_cents=amount_cents, note=note,
                ))
            else:
                logger.warning("无效选项，未批准、未记账。")
        except (EOFError, KeyboardInterrupt):
            review.reject(review.state.proposal.id)
        except ValueError as exc:
            logger.error("{}", exc)
    logger.info("本次结束：{}；模拟账本：{} 笔。退出后内存账本不保留。", review.state.status, len(review.ledger))


def main() -> None:
    logger.info("E07 本地实验：只写入内存模拟账本，不进行真实付款。")
    run(PaymentApproval(PaymentArguments(
        recipient="示例供应商 A", amount_cents=12500, note="模拟购买学习资料",
    )))


if __name__ == "__main__":
    main()
