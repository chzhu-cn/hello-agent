"""SQLite 中的一行就是一次模拟记账，操作 ID 唯一。"""

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID

from logly import logger

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.schemas.ledger import PaymentOperation


class PaymentLedger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS payments "
                "(operation_id TEXT PRIMARY KEY, payment_json TEXT NOT NULL)"
            )

    def execute(self, operation: PaymentOperation, *, lose_response: bool = False) -> PaymentOperation:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            # 查询和写入在同一写事务里，避免两个调用同时通过“不存在”检查。
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payment_json FROM payments WHERE operation_id = ?",
                (str(operation.operation_id),),
            ).fetchone()
            if row is not None:
                stored = PaymentArguments.model_validate_json(row[0])
                if stored != operation.payment:
                    raise ValueError("同一操作 ID 已绑定不同参数，拒绝记账")
                logger.info("命中已有记录，不重复记账：{}", operation.operation_id)
            else:
                connection.execute(
                    "INSERT INTO payments (operation_id, payment_json) VALUES (?, ?)",
                    (str(operation.operation_id), operation.payment.model_dump_json()),
                )
        # 到这里事务已经提交；注入故障模拟结果未到达调用方。
        if lose_response:
            raise TimeoutError("模拟响应丢失：账本已提交，但调用方未收到结果")
        return operation

    def query(self, operation_id: UUID) -> PaymentOperation | None:
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT payment_json FROM payments WHERE operation_id = ?", (str(operation_id),),
            ).fetchone()
        if row is None:
            return None
        return PaymentOperation(
            operation_id=operation_id, payment=PaymentArguments.model_validate_json(row[0]),
        )

    def count(self) -> int:
        with closing(sqlite3.connect(self.path)) as connection:
            return connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
