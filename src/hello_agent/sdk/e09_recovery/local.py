"""审批检查点体验：uv run python -m hello_agent.sdk.e09_recovery.local"""

from logly import logger

from hello_agent.config.settings import checkpoint_config
from hello_agent.schemas.approval import PaymentArguments
from hello_agent.tools.approval import PaymentApproval
from hello_agent.tools.checkpoint import load_approval, save_approval


def main() -> None:
    path = checkpoint_config.path
    try:
        saved = load_approval(path)
    except FileNotFoundError:
        review = PaymentApproval(PaymentArguments(
            recipient="示例供应商 A", amount_cents=12500, note="E09 检查点实验",
        ))
        save_approval(path, review.state)
    else:
        review = PaymentApproval.restore(saved)
    logger.info("本步只保存审批状态，不执行付款或写入账本。")
    while True:
        proposal = review.state.proposal
        payment = proposal.payment
        logger.info(
            "提案 ID：{}；状态：{}\n收款人：{}；金额：{}.{:02d} {}；用途：{}",
            proposal.id, review.state.status, payment.recipient,
            payment.amount_cents // 100, payment.amount_cents % 100, payment.currency, payment.note,
        )
        if review.state.status == "rejected":
            return
        logger.info("a 批准并保存退出；r 拒绝并保存退出；m 修改并保存；q 保留状态退出。")
        try:
            action = input().strip().lower()
            if action == "q":
                return
            if action == "a":
                review.approve(proposal.id)
            elif action == "r":
                review.reject(proposal.id)
            elif action == "m":
                logger.info("新收款人：")
                recipient = input()
                logger.info("新金额（整数分）：")
                amount_cents = int(input())
                logger.info("新用途：")
                note = input()
                review.revise(PaymentArguments(recipient=recipient, amount_cents=amount_cents, note=note))
            else:
                logger.warning("无效选项，状态未改变。")
                continue
        except (EOFError, KeyboardInterrupt):
            logger.info("退出，保留上次已保存的状态。")
            return
        except ValueError as exc:
            logger.error("{}", exc)
            continue
        # 保存失败直接终止，不继续用仅存在于内存的新状态进行操作。
        save_approval(path, review.state)
        if action in ("a", "r"):
            return


if __name__ == "__main__":
    main()
