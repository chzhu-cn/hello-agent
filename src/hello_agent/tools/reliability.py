"""只为明确支持幂等的执行接口提供有限重试。"""

from collections.abc import Callable
from uuid import UUID

from logly import logger

from hello_agent.schemas.config import RetryConfig
from hello_agent.schemas.ledger import ExecutionOutcome, ExecutionStatus, PaymentOperation
from hello_agent.tools.ledger import IdempotencyConflict


def execute_with_retries(
    operation: PaymentOperation,
    execute: Callable[[PaymentOperation], PaymentOperation],
    query: Callable[[UUID], PaymentOperation | None],
    policy: RetryConfig,
) -> ExecutionOutcome:
    queries = 0
    status: ExecutionStatus
    for attempt in range(1, policy.max_attempts + 1):
        logger.info("执行尝试 {}/{}；操作 ID：{}", attempt, policy.max_attempts, operation.operation_id)
        try:
            result = execute(operation)
        except IdempotencyConflict:
            status, reason = "rejected", "操作 ID 与参数冲突，不重试"
        except (TimeoutError, ConnectionError):
            logger.warning("执行结果未确认，先查询原操作 ID。")
            queries += 1
            try:
                result = query(operation.operation_id)
            except Exception as exc:
                status, reason = "unknown", f"查询失败：{type(exc).__name__}，停止重发"
            else:
                if result == operation:
                    status, reason = "succeeded", "查询确认已成功，无需再次执行"
                elif result is not None:
                    status, reason = "unknown", "查询返回的操作或参数不匹配，停止重发"
                elif attempt < policy.max_attempts:
                    logger.info("暂未查到记录；依赖工具幂等保证，使用相同 ID 与参数重试。")
                    continue
                else:
                    status, reason = "unknown", "尝试次数已耗尽，仍未确认执行结果"
        except Exception as exc:
            # 没有针对这类错误的重试约定，不能把它当作确定未执行。
            status, reason = "unknown", f"未分类执行异常：{type(exc).__name__}，停止重发"
        else:
            if result == operation:
                status, reason = "succeeded", "收到匹配的成功响应"
            else:
                status, reason = "unknown", "执行响应与请求不匹配，停止重发"
        return ExecutionOutcome(
            operation_id=operation.operation_id, status=status,
            attempts=attempt, queries=queries, reason=reason,
        )
    raise RuntimeError("重试次数配置无效")
