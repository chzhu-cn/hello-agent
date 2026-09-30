"""有限重试不会把未知结果当作确定失败。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.schemas.config import RetryConfig
from hello_agent.schemas.ledger import PaymentOperation
from hello_agent.tools.ledger import PaymentLedger
from hello_agent.tools.reliability import execute_with_retries


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = PaymentLedger(Path(self.temp.name) / "ledger.sqlite3")
        self.operation = PaymentOperation(
            operation_id=uuid4(),
            payment=PaymentArguments(recipient="示例 A", amount_cents=12500, note="测试"),
        )
        self.policy = RetryConfig(_env_file=None, max_attempts=3)

    def test_retry_reuses_id_and_parameters(self):
        calls = []

        def execute(operation):
            calls.append(operation)
            if len(calls) == 1:
                raise TimeoutError()
            return self.ledger.execute(operation)

        result = execute_with_retries(self.operation, execute, self.ledger.query, self.policy)
        self.assertEqual((result.status, result.attempts, result.queries), ("succeeded", 2, 1))
        self.assertEqual(calls, [self.operation, self.operation])
        self.assertEqual(self.ledger.count(), 1)

    def test_committed_timeout_queries_without_reexecution(self):
        execute = Mock(side_effect=lambda operation: self.ledger.execute(operation, lose_response=True))
        result = execute_with_retries(self.operation, execute, self.ledger.query, self.policy)
        self.assertEqual((result.status, result.attempts, result.queries), ("succeeded", 1, 1))
        execute.assert_called_once_with(self.operation)
        self.assertEqual(self.ledger.count(), 1)

    def test_query_failure_retains_unknown_despite_commit(self):
        execute = Mock(side_effect=lambda operation: self.ledger.execute(operation, lose_response=True))
        query = Mock(side_effect=ConnectionError())
        result = execute_with_retries(self.operation, execute, query, self.policy)
        self.assertEqual(result.status, "unknown")
        execute.assert_called_once()
        query.assert_called_once_with(self.operation.operation_id)
        self.assertEqual(self.ledger.count(), 1)

    def test_budget_exhaustion_is_unknown_and_queries_last_attempt(self):
        for limit in (1, 3):
            with self.subTest(limit=limit):
                execute = Mock(side_effect=TimeoutError())
                query = Mock(return_value=None)
                result = execute_with_retries(
                    self.operation, execute, query, RetryConfig(_env_file=None, max_attempts=limit),
                )
                self.assertEqual((result.status, result.attempts, result.queries), ("unknown", limit, limit))
                self.assertEqual(execute.call_count, limit)
                self.assertEqual(query.call_count, limit)

    def test_conflict_is_rejected_without_query_or_retry(self):
        self.ledger.execute(self.operation)
        changed = PaymentOperation(
            operation_id=self.operation.operation_id,
            payment=PaymentArguments(recipient="示例 B", amount_cents=9900, note="测试"),
        )
        execute = Mock(wraps=self.ledger.execute)
        query = Mock(wraps=self.ledger.query)
        result = execute_with_retries(changed, execute, query, self.policy)
        self.assertEqual(result.status, "rejected")
        execute.assert_called_once()
        query.assert_not_called()
        self.assertEqual(self.ledger.query(self.operation.operation_id), self.operation)

    def test_unclassified_error_and_mismatched_response_stop(self):
        query = Mock()
        for execute in (Mock(side_effect=RuntimeError()), Mock(return_value=None)):
            result = execute_with_retries(self.operation, execute, query, self.policy)
            self.assertEqual(result.status, "unknown")
            execute.assert_called_once()
        query.assert_not_called()

    def test_mismatched_query_stops(self):
        other = PaymentOperation(operation_id=uuid4(), payment=self.operation.payment)
        execute = Mock(side_effect=TimeoutError())
        result = execute_with_retries(self.operation, execute, Mock(return_value=other), self.policy)
        self.assertEqual(result.status, "unknown")
        execute.assert_called_once()
