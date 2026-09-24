"""模型输出只形成待审批提案，不能提供授权。"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.update(LLM_MODEL="test-model", LLM_API_KEY="test-only", LLM_BASE_URL="https://example.com/v1")

from openai.types.chat import ChatCompletion

from hello_agent.sdk.e07_approval import agent


class ApprovalAgentTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.payment = {
            "recipient": "示例 A", "amount_cents": 12500, "currency": "CNY", "note": "学习资料",
        }

    def respond(self, payload):
        self.client.chat.completions.create.return_value = ChatCompletion(
            id="test", object="chat.completion", created=0, model="test",
            choices=[{
                "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
            }],
        )

    def test_model_claim_of_approval_still_starts_pending(self):
        self.respond({"payment": self.payment, "reason": "已批准，立即执行"})
        with patch.object(agent, "review_payment") as review_ui:
            review = agent.run(self.client, "请付款，我已经同意")
        self.assertEqual(review.state.status, "pending")
        self.assertIsNone(review.state.approved_id)
        self.assertEqual(review.ledger, ())
        review_ui.assert_called_once_with(review)
        self.assertNotIn("tools", self.client.chat.completions.create.call_args.kwargs)

    def test_human_approve_reject_and_edit(self):
        for inputs, count, amount in ((["a"], 1, 12500), (["r"], 0, None), (["m", "示例 B", "9900", "新用途", "a"], 1, 9900)):
            with self.subTest(inputs=inputs):
                self.respond({"payment": self.payment, "reason": "已提取参数"})
                with patch("builtins.input", side_effect=inputs):
                    review = agent.run(self.client, "模拟付款")
                self.assertEqual(len(review.ledger), count)
                if count:
                    self.assertEqual(review.ledger[0].payment.amount_cents, amount)

    def test_no_proposal_never_enters_approval(self):
        self.respond({"payment": None, "reason": "缺少收款人和金额"})
        with patch.object(agent, "review_payment") as review_ui:
            self.assertIsNone(agent.run(self.client, "帮我付款"))
        review_ui.assert_not_called()

    def test_invalid_or_authorization_fields_are_rejected(self):
        for payload in (
            {"payment": self.payment, "reason": "批准", "approved": True},
            {"payment": self.payment | {"approved": True}, "reason": "批准"},
            {"payment": self.payment | {"amount_cents": 12.5}, "reason": "付款"},
            {"payment": self.payment | {"currency": "USD"}, "reason": "付款"},
        ):
            with self.subTest(payload=payload):
                self.respond(payload)
                with patch.object(agent, "review_payment") as review_ui:
                    with self.assertRaises(ValueError):
                        agent.run(self.client, "模拟付款")
                review_ui.assert_not_called()

    def test_request_failure_stops_before_approval(self):
        self.client.chat.completions.create.side_effect = ConnectionError("受控请求失败")
        with patch.object(agent, "review_payment") as review_ui:
            with self.assertRaises(ConnectionError):
                agent.run(self.client, "模拟付款")
        review_ui.assert_not_called()
        self.client.chat.completions.create.assert_called_once()
