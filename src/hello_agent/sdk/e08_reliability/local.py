"""固定模拟操作：uv run python -m hello_agent.sdk.e08_reliability.local"""

from uuid import UUID

from logly import logger

from hello_agent.config.settings import ledger_config
from hello_agent.schemas.approval import PaymentArguments
from hello_agent.schemas.ledger import PaymentOperation
from hello_agent.tools.ledger import PaymentLedger


def main() -> None:
    # 固定实验 ID，重复启动仍代表同一笔操作，不能每次重试生成新 ID。
    operation = PaymentOperation(
        operation_id=UUID("00000000-0000-0000-0000-000000000007"),
        payment=PaymentArguments(recipient="示例供应商 A", amount_cents=12500, note="E08 固定模拟操作"),
    )
    ledger = PaymentLedger(ledger_config.path)
    before = ledger.count()
    logger.info("E08 独立模拟实验；账本：{}；原有记录：{} 笔", ledger_config.path, before)
    try:
        ledger.execute(operation, lose_response=True)
    except TimeoutError:
        logger.warning("未收到执行结果，当前结果未知，先按原操作 ID 查询。")
    found = ledger.query(operation.operation_id)
    if found != operation:
        raise ValueError("未查到匹配的成功记录，不自动重新执行")
    logger.info("已查到匹配记录，确认执行成功：{}", found.operation_id)
    # 仅为验证幂等再发一次同键请求；真实流程查到成功即可结束。
    ledger.execute(operation)
    logger.success("同键重发后账本共 {} 笔，本次新增 {} 笔", ledger.count(), ledger.count() - before)


if __name__ == "__main__":
    main()
