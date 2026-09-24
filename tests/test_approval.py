"""E07：批准绑定提案，修改、拒绝与退出均不能偷偷记账。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from hello_agent.schemas.approval import PaymentArguments
from hello_agent.sdk.e07_approval.local import run
from hello_agent.tools.approval import PaymentApproval


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.payment = PaymentArguments(recipient="示例 A", amount_cents=12500, note="学习资料")
        self.review = PaymentApproval(self.payment)

    def test_only_current_approval_allows_one_execution(self):
        with self.assertRaisesRegex(ValueError, "尚未批准"):
            self.review.execute()
        self.assertEqual(self.review.ledger, ())
        self.review.approve(self.review.state.proposal.id)
        self.assertEqual(self.review.ledger, ())
        receipt = self.review.execute()
        self.assertEqual(receipt.payment, self.payment)
        self.assertEqual(receipt.proposal_id, self.review.state.proposal.id)
        with self.assertRaises(ValueError):
            self.review.execute()
        self.assertEqual(len(self.review.ledger), 1)

    def test_rejection_is_terminal_and_has_no_entry(self):
        self.review.reject(self.review.state.proposal.id)
        with self.assertRaises(ValueError):
            self.review.execute()
        with self.assertRaises(ValueError):
            self.review.approve(self.review.state.proposal.id)
        self.assertEqual(self.review.ledger, ())

    def test_each_parameter_change_invalidates_approval(self):
        for change in (
            {"recipient": "示例 B"}, {"amount_cents": 20000}, {"note": "其他用途"},
        ):
            with self.subTest(change=change):
                review = PaymentApproval(self.payment)
                old_id = review.state.proposal.id
                review.approve(old_id)
                updated = PaymentArguments.model_validate(self.payment.model_dump() | change)
                review.revise(updated)
                self.assertNotEqual(review.state.proposal.id, old_id)
                self.assertIsNone(review.state.approved_id)
                with self.assertRaises(ValueError):
                    review.execute()
                with self.assertRaises(ValueError):
                    review.approve(old_id)
                self.assertEqual(review.ledger, ())
                review.approve(review.state.proposal.id)
                self.assertEqual(review.execute().payment, updated)

    def test_unrelated_approval_and_direct_mutation_are_rejected(self):
        with self.assertRaises(ValueError):
            self.review.approve(uuid4())
        with self.assertRaises(ValidationError):
            self.review.state.proposal.payment.amount_cents = 1
        self.assertEqual(self.review.state.status, "pending")
        self.assertEqual(self.review.ledger, ())

    def test_interactive_modify_then_approve(self):
        with patch("builtins.input", side_effect=["m", "示例 B", "9900", "新用途", "a"]):
            run(self.review)
        self.assertEqual(len(self.review.ledger), 1)
        self.assertEqual(self.review.ledger[0].payment.amount_cents, 9900)
        self.assertEqual(self.review.ledger[0].payment.recipient, "示例 B")

    def test_invalid_input_and_eof_never_approve(self):
        with patch("builtins.input", side_effect=["yes", "m", "示例 B", "0", "新用途", EOFError()]):
            run(self.review)
        self.assertEqual(self.review.state.status, "rejected")
        self.assertEqual(self.review.ledger, ())
        self.assertEqual(self.review.state.proposal.payment, self.payment)

    def test_payment_rejects_invalid_amount_or_recipient(self):
        for change in ({"amount_cents": 0}, {"amount_cents": -1}, {"amount_cents": 1.5}, {"amount_cents": True}, {"recipient": "  "}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                PaymentArguments.model_validate(self.payment.model_dump() | change)
