"""本地故障注入：uv run python -m hello_agent.sdk.e08_reliability.retry"""

import argparse
from uuid import UUID, uuid4

from logly import logger

from hello_agent.config.settings import ledger_config, retry_config
from hello_agent.schemas.approval import PaymentArguments
from hello_agent.schemas.ledger import PaymentOperation
from hello_agent.tools.ledger import PaymentLedger
from hello_agent.tools.reliability import execute_with_retries


def main() -> None:
    parser = argparse.ArgumentParser(description="E08-B 本地超时与有限重试模拟")
    parser.add_argument("scenario", nargs="?", default="before-timeout", choices=[
        "before-timeout", "after-timeout", "query-unavailable", "always-timeout", "conflict",
    ])
    args = parser.parse_args()
    # 每次启动是一个新实验；单次实验内的全部尝试共用此 ID。
    operation = PaymentOperation(
        operation_id=uuid4(),
        payment=PaymentArguments(recipient="示例供应商 A", amount_cents=12500, note="E08-B 模拟操作"),
    )
    ledger = PaymentLedger(ledger_config.path)
    before = ledger.count()
    if args.scenario == "conflict":
        ledger.execute(PaymentOperation(
            operation_id=operation.operation_id,
            payment=PaymentArguments(recipient="示例供应商 A", amount_cents=9900, note="E08-B 模拟操作"),
        ))
    calls = 0

    def execute(current: PaymentOperation) -> PaymentOperation:
        nonlocal calls
        calls += 1
        if args.scenario == "always-timeout" or (args.scenario == "before-timeout" and calls == 1):
            raise TimeoutError("注入提交前超时")
        return ledger.execute(current, lose_response=args.scenario in ("after-timeout", "query-unavailable"))

    def query(operation_id: UUID) -> PaymentOperation | None:
        if args.scenario == "query-unavailable":
            raise ConnectionError("注入查询不可用")
        return ledger.query(operation_id)

    result = execute_with_retries(operation, execute, query, retry_config)
    logger.info("最终状态：{}；尝试：{}；查询：{}；原因：{}", result.status, result.attempts, result.queries, result.reason)
    # 实验者直接查看存储，不作为上面调用方可获得的查询结果。
    logger.info("实验侧账本核对：本次新增 {} 笔（conflict 包含预置记录）", ledger.count() - before)


if __name__ == "__main__":
    main()
