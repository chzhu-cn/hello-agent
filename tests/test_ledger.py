"""持久幂等记录、参数冲突与提交后响应丢失。"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.schemas.ledger import PaymentOperation
from hello_agent.tools.ledger import PaymentLedger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.sqlite3"
        self.ledger = PaymentLedger(self.path)
        self.operation = PaymentOperation(
            operation_id=uuid4(),
            payment=PaymentArguments(recipient="示例 A", amount_cents=12500, note="学习资料"),
        )

    def test_same_key_same_parameters_writes_once(self):
        self.assertIsNone(self.ledger.query(self.operation.operation_id))
        self.assertEqual(self.ledger.execute(self.operation), self.operation)
        self.assertEqual(self.ledger.execute(self.operation), self.operation)
        self.assertEqual(self.ledger.count(), 1)

    def test_conflicting_parameters_never_overwrite(self):
        self.ledger.execute(self.operation)
        for change in ({"recipient": "示例 B"}, {"amount_cents": 9900}, {"note": "另一用途"}):
            with self.subTest(change=change):
                payment = PaymentArguments.model_validate(self.operation.payment.model_dump() | change)
                with self.assertRaises(ValueError):
                    self.ledger.execute(PaymentOperation(operation_id=self.operation.operation_id, payment=payment))
                self.assertEqual(self.ledger.query(self.operation.operation_id), self.operation)
                self.assertEqual(self.ledger.count(), 1)

    def test_response_loss_then_new_process_retry(self):
        with self.assertRaises(TimeoutError):
            self.ledger.execute(self.operation, lose_response=True)
        # 用新进程读取和重发，不能依赖原实例的内存状态。
        code = (
            "import sys; from pathlib import Path; "
            "from hello_agent.tools.ledger import PaymentLedger; "
            "from hello_agent.schemas.ledger import PaymentOperation; "
            "operation = PaymentOperation.model_validate_json(sys.argv[2]); "
            "ledger = PaymentLedger(Path(sys.argv[1])); "
            "assert ledger.query(operation.operation_id) == operation; "
            "assert ledger.execute(operation) == operation; "
            "assert ledger.count() == 1"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(self.path), self.operation.model_dump_json()],
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ledger.count(), 1)

    def test_new_key_is_a_new_operation(self):
        self.ledger.execute(self.operation)
        self.ledger.execute(PaymentOperation(operation_id=uuid4(), payment=self.operation.payment))
        self.assertEqual(self.ledger.count(), 2)
