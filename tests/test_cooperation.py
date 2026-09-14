"""P4 的交接、权限隔离、记录与失败传播。"""

from copy import deepcopy
import json
import unittest
from unittest.mock import MagicMock, patch

from openai import APIConnectionError

from test_tool_call import response, call
from hello_agent.sdk.p04_multi_agent import agent

DELEGATE = '{"recipient":"calculator","instruction":"先算127+358，再加96"}'


class CooperationTests(unittest.TestCase):
    def setUp(self):
        setting = patch.object(agent.cooperation_config, "worker_max_steps", 5)
        setting.start()
        self.addCleanup(setting.stop)

    def client(self, replies):
        client = MagicMock()
        snapshots = []
        replies = iter(replies)
        def create(**kwargs):
            snapshots.append(deepcopy(kwargs))
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply
        client.chat.completions.create.side_effect = create
        return client, snapshots

    def normal(self):
        return [response(DELEGATE), response(calls=[call()]),
                response(calls=[call(arguments='{"a":485,"b":96}', id="second")]),
                response("485，581"), response("127+358=485；485+96=581。")]

    def test_normal_and_context_permissions(self):
        client, requests = self.client(self.normal())
        result = agent.run(client)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.total_requests, 5)
        self.assertEqual(result.coordinator_requests, 2)
        self.assertEqual([r.result for r in result.worker.records], [485, 581])
        for i in (0, 4):
            self.assertNotIn("tools", requests[i])
            self.assertFalse(any(m["role"] == "tool" for m in requests[i]["messages"]))
        for i in (1, 2, 3):
            self.assertEqual(requests[i]["tools"][0]["function"]["name"], "add")
        self.assertEqual(len(requests[1]["messages"]), 2)
        payload = json.loads(requests[1]["messages"][1]["content"])
        self.assertEqual(payload["original_task"], agent.TASK)
        self.assertEqual(payload["delegation"]["recipient"], "calculator")
        self.assertEqual(requests[2]["messages"][-1]["tool_call_id"], "call_1")
        self.assertEqual(json.loads(requests[2]["messages"][-1]["content"])["result"], 485)
        self.assertIn('"result":581.0', requests[4]["messages"][-2]["content"])

    def test_bad_delegation_never_starts_worker(self):
        for text in ('bad', '{"recipient":"other","instruction":"计算"}',
                     '{"recipient":"calculator","instruction":" "}'):
            with self.subTest(text=text), patch.object(agent, "add") as add:
                client, requests = self.client([response(text)])
                result = agent.run(client)
                self.assertEqual(result.status, "failed")
                self.assertIsNone(result.worker)
                self.assertEqual(len(requests), 1)
                add.assert_not_called()

    def test_invalid_worker_calls_not_executed(self):
        for calls in ([call(name="delegate")], [call(arguments='{}')],
                      [call(), call(id="second")], [call(id="")]):
            with self.subTest(calls=calls), patch.object(agent, "add") as add:
                client, requests = self.client([response(DELEGATE), response(calls=calls)])
                result = agent.run(client)
                self.assertEqual(result.worker.status, "failed")
                self.assertEqual(len(requests), 2)
                add.assert_not_called()

    def test_failure_preserves_records_without_summary(self):
        client, requests = self.client(self.normal())
        with patch.object(agent, "add", side_effect=[485, RuntimeError("failure")]) as add:
            result = agent.run(client)
        self.assertEqual(result.status, "failed")
        self.assertEqual([r.result for r in result.worker.records], [485])
        self.assertEqual(add.call_count, 2)
        self.assertEqual(len(requests), 3)

    def test_limit_does_not_execute_last_tool(self):
        client, requests = self.client(self.normal())
        with patch.object(agent.cooperation_config, "worker_max_steps", 2), patch.object(agent, "add", wraps=agent.add) as add:
            result = agent.run(client)
        self.assertEqual(result.status, "failed")
        self.assertIn("上限", result.error)
        self.assertEqual(add.call_count, 1)
        self.assertEqual(len(requests), 3)

    def test_no_records_cannot_complete(self):
        client, _ = self.client([response(DELEGATE), response("581")])
        result = agent.run(client)
        self.assertEqual(result.status, "failed")
        self.assertIn("没有执行工具", result.error)

    def test_model_failure_at_each_role(self):
        for index in (0, 1, 4):
            with self.subTest(index=index):
                replies = self.normal()[:index]
                replies.append(APIConnectionError(request=MagicMock()))
                client, requests = self.client(replies)
                result = agent.run(client)
                self.assertEqual(result.status, "failed")
                self.assertEqual(len(requests), index + 1)
                self.assertEqual(result.total_requests, index + 1)

    def test_incomplete_worker_response(self):
        for reply in (response(""), response("partial"), response(calls=[call()])):
            if reply.choices[0].message.content or reply.choices[0].message.tool_calls:
                reply.choices[0].finish_reason = "length"
            client, _ = self.client([response(DELEGATE), reply])
            with patch.object(agent, "add") as add:
                self.assertEqual(agent.run(client).status, "failed")
                add.assert_not_called()

    def test_wrong_tool_evidence_is_not_proof_of_correctness(self):
        replies = self.normal()
        replies[2] = response(calls=[call(arguments='{"a":486,"b":96}')])
        replies[3:] = [response("583"), response("583")]
        client, _ = self.client(replies)
        with patch.object(agent, "add", side_effect=[486, 583]):
            result = agent.run(client)
        self.assertEqual(result.status, "completed")
        self.assertNotEqual(result.worker.records[-1].result, 581)
        self.assertEqual(result.answer, "583")

    def test_wrapped_responses_use_llm_cleanup(self):
        replies = self.normal()
        replies[0] = response(f"<think>委派</think>```json\n{DELEGATE}\n```")
        replies[3] = response("<think>计算</think>581")
        replies[4] = response("<think>汇总</think>581")
        client, _ = self.client(replies)
        result = agent.run(client)
        self.assertEqual(result.answer, "581")
        self.assertEqual(result.worker.answer, "581")
