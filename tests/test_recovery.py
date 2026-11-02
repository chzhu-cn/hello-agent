"""执行前后真实进程退出，恢复不会盲目重跑。"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.tools.approval import PaymentApproval
from hello_agent.tools.ledger import PaymentLedger
from hello_agent.tools.recovery import (
    execute_saved, load_execution, prepare_execution, recover_execution,
)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "execution.json"
        self.db_path = Path(self.temp.name) / "ledger.sqlite3"
        self.ledger = PaymentLedger(self.db_path)
        self.review = PaymentApproval(PaymentArguments(recipient="示例 A", amount_cents=12500, note="测试"))

    def prepare(self):
        self.review.approve(self.review.state.proposal.id)
        return prepare_execution(self.path, self.review.state)

    def crash_process(self, stage):
        code = (
            "import os, sys; from pathlib import Path; "
            "from hello_agent.tools.recovery import execute_saved; "
            "from hello_agent.tools.ledger import PaymentLedger; "
            "execute_saved(Path(sys.argv[1]), PaymentLedger(Path(sys.argv[2])), "
            "interrupt=lambda stage: os._exit(73) if stage == sys.argv[3] else None)"
        )
        process = subprocess.run(
            [sys.executable, "-c", code, str(self.path), str(self.db_path), stage],
            capture_output=True, timeout=15,
        )
        self.assertEqual(process.returncode, 73, process.stderr)
        self.assertEqual(load_execution(self.path).phase, "executing")

    def test_unapproved_proposal_cannot_prepare(self):
        with self.assertRaises(ValueError):
            prepare_execution(self.path, self.review.state)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.ledger.count(), 0)

    def test_cli_rejects_inconsistent_approval_without_changing_files(self):
        approval_path = self.path.parent / "approval.json"
        invalid = {
            "version": 1,
            "state": self.review.state.model_dump(mode="json") | {"status": "approved"},
        }
        approval_path.write_text(json.dumps(invalid), encoding="utf-8")
        before = approval_path.read_bytes()
        env = os.environ.copy() | {
            "LLM_MODEL": "test-model", "LLM_API_KEY": "test-only",
            "CHECKPOINT_PATH": str(approval_path), "CHECKPOINT_EXECUTION_PATH": str(self.path),
            "LEDGER_PATH": str(self.path.parent / "unused.sqlite3"),
        }
        for module, args in (("local", []), ("execution", ["execute"])):
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", "-m", f"hello_agent.sdk.e09_recovery.{module}", *args],
                    env=env, capture_output=True, text=True, encoding="utf-8", timeout=15,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("审批检查点校验失败", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)
                self.assertEqual(approval_path.read_bytes(), before)
                self.assertFalse(self.path.exists())
                self.assertFalse((self.path.parent / "unused.sqlite3").exists())

    def test_normal_success_and_repeated_resume_do_not_execute_again(self):
        checkpoint = self.prepare()
        self.assertEqual(prepare_execution(self.path, self.review.state), checkpoint)
        result = execute_saved(self.path, self.ledger)
        self.assertEqual(result.phase, "succeeded")
        self.assertEqual(result.result.operation_id, self.review.state.proposal.id)
        with patch.object(self.ledger, "execute") as execute, patch.object(self.ledger, "query") as query:
            self.assertEqual(execute_saved(self.path, self.ledger), result)
            execute.assert_not_called()
            query.assert_not_called()
        self.assertEqual(self.ledger.count(), 1)

    def test_crash_after_commit_recovers_success_without_reexecution(self):
        self.prepare()
        self.crash_process("after-call")
        self.assertEqual(self.ledger.count(), 1)
        with patch.object(self.ledger, "execute") as execute:
            result = recover_execution(self.path, self.ledger)
            execute.assert_not_called()
        self.assertEqual(result.phase, "succeeded")
        self.assertEqual(result.result.payment, self.review.state.proposal.payment)
        self.assertEqual(self.ledger.count(), 1)

    def test_crash_before_call_remains_unknown_without_reexecution(self):
        self.prepare()
        self.crash_process("before-call")
        with patch.object(self.ledger, "execute") as execute:
            self.assertEqual(execute_saved(self.path, self.ledger).phase, "unknown")
            execute.assert_not_called()
        self.assertEqual(self.ledger.count(), 0)

    def test_query_failure_retains_unknown_then_can_query_again(self):
        self.prepare()
        self.crash_process("after-call")
        with patch.object(self.ledger, "query", side_effect=ConnectionError()):
            self.assertEqual(recover_execution(self.path, self.ledger).phase, "unknown")
        self.assertEqual(recover_execution(self.path, self.ledger).phase, "succeeded")
        self.assertEqual(self.ledger.count(), 1)

    def test_save_before_execution_failure_never_calls_tool(self):
        self.prepare()
        with patch("hello_agent.tools.recovery.save_execution", side_effect=OSError()), patch.object(self.ledger, "execute") as execute:
            with self.assertRaises(OSError):
                execute_saved(self.path, self.ledger)
            execute.assert_not_called()
        self.assertEqual(load_execution(self.path).phase, "approved")

    def test_save_result_failure_can_recover_via_ledger(self):
        self.prepare()
        from hello_agent.tools.recovery import save_execution

        def save(path, checkpoint):
            if checkpoint.phase == "succeeded":
                raise OSError("受控结果保存失败")
            save_execution(path, checkpoint)

        with patch("hello_agent.tools.recovery.save_execution", side_effect=save):
            with self.assertRaises(OSError):
                execute_saved(self.path, self.ledger)
        self.assertEqual(load_execution(self.path).phase, "executing")
        self.assertEqual(recover_execution(self.path, self.ledger).phase, "succeeded")
        self.assertEqual(self.ledger.count(), 1)

    def test_new_approval_cannot_overwrite_existing_execution(self):
        self.prepare()
        self.review.revise(PaymentArguments(recipient="示例 B", amount_cents=9900, note="修改"))
        self.review.approve(self.review.state.proposal.id)
        with self.assertRaises(ValueError):
            prepare_execution(self.path, self.review.state)
