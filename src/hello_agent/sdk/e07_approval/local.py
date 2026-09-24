"""本地审批体验：uv run python -m hello_agent.sdk.e07_approval.local"""

from logly import logger

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.tools.approval import PaymentApproval
from hello_agent.tools.approval_ui import run


def main() -> None:
    logger.info("E07 本地实验：只写入内存模拟账本，不进行真实付款。")
    run(PaymentApproval(PaymentArguments(
        recipient="示例供应商 A", amount_cents=12500, note="模拟购买学习资料",
    )))


if __name__ == "__main__":
    main()
