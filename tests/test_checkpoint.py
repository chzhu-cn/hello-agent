"""执行前审批状态跨进程恢复及不完整文件拒绝。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.tools.approval import PaymentApproval
from hello_agent.tools.checkpoint import load_approval, save_approval


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "checkpoint.json"
        self.review = PaymentApproval(PaymentArguments(recipient="示例 A", amount_cents=12500, note="测试"))

    def test_pending_survives_new_process_without_approval(self):
        save_approval(self.path, self.review.state)
        code = (
            "import sys; from pathlib import Path; "
            "from hello_agent.tools.checkpoint import load_approval; "
            "from hello_agent.tools.approval import PaymentApproval; "
            "review = PaymentApproval.restore(load_approval(Path(sys.argv[1]))); "
            "assert str(review.state.proposal.id) == sys.argv[2]; "
            "assert review.state.status == 'pending'; "
            "assert review.state.approved_id is None; assert review.ledger == ()"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(self.path), str(self.review.state.proposal.id)],
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        restored = PaymentApproval.restore(load_approval(self.path))
        with self.assertRaises(ValueError):
            restored.execute()

    def test_approved_restore_preserves_identity_and_revision_invalidates(self):
        proposal_id = self.review.state.proposal.id
        self.review.approve(proposal_id)
        save_approval(self.path, self.review.state)
        restored = PaymentApproval.restore(load_approval(self.path))
        self.assertEqual(restored.state, self.review.state)
        self.assertEqual(restored.ledger, ())
        restored.revise(PaymentArguments(recipient="示例 B", amount_cents=9900, note="修改"))
        save_approval(self.path, restored.state)
        changed = PaymentApproval.restore(load_approval(self.path))
        self.assertIsNone(changed.state.approved_id)
        with self.assertRaises(ValueError):
            changed.approve(proposal_id)
        with self.assertRaises(ValueError):
            changed.execute()

    def test_rejected_restores_as_terminal(self):
        self.review.reject(self.review.state.proposal.id)
        save_approval(self.path, self.review.state)
        restored = PaymentApproval.restore(load_approval(self.path))
        with self.assertRaises(ValueError):
            restored.approve(restored.state.proposal.id)
        self.assertEqual(restored.state.status, "rejected")

    def test_invalid_checkpoint_never_silently_defaults(self):
        save_approval(self.path, self.review.state)
        original = self.path.read_text(encoding="utf-8")
        for case in ("missing-id", "missing-status", "missing-approved-id", "mismatched-approval", "unsupported-version", "broken-json"):
            with self.subTest(case=case):
                content = json.loads(original)
                if case == "missing-id":
                    del content["state"]["proposal"]["id"]
                elif case == "missing-status":
                    del content["state"]["status"]
                elif case == "missing-approved-id":
                    del content["state"]["approved_id"]
                elif case == "mismatched-approval":
                    content["state"].update(status="approved", approved_id=str(uuid4()))
                elif case == "unsupported-version":
                    content["version"] = 2
                self.path.write_text("{" if case == "broken-json" else json.dumps(content), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    load_approval(self.path)

    def test_failed_replace_preserves_previous_checkpoint(self):
        save_approval(self.path, self.review.state)
        before = self.path.read_bytes()
        self.review.approve(self.review.state.proposal.id)
        with patch.object(Path, "replace", side_effect=OSError("受控写入失败")):
            with self.assertRaises(OSError):
                save_approval(self.path, self.review.state)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_executed_state_is_outside_this_step(self):
        self.review.approve(self.review.state.proposal.id)
        self.review.execute()
        with self.assertRaises(ValidationError):
            save_approval(self.path, self.review.state)
        with self.assertRaises(ValueError):
            PaymentApproval.restore(self.review.state)
        self.assertFalse(self.path.exists())
