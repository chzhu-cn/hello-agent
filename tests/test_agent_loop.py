"""使用受控响应验证循环和停止条件。"""

from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

from test_tool_call import response, call
from hello_agent.sdk.p01_react import agent


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(agent.agent_config, 'max_steps', 5)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sequential_results(self):
        client = MagicMock()
        replies = iter([response(calls=[call()]), response(calls=[call(arguments='{"a":485,"b":96}', id='second')]), response('581')])
        requests = []
        def request(**kwargs):
            requests.append(deepcopy(kwargs))
            return next(replies)
        client.chat.completions.create.side_effect = request
        self.assertEqual(agent.run(client, '计算'), '581')
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[1]['messages'][-1]['content'], '{"result":485.0}')
        self.assertEqual(requests[2]['messages'][-1]['content'], '{"result":581.0}')
        self.assertEqual(requests[2]['messages'][-1]['tool_call_id'], 'second')

    def test_direct_answer(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response('你好')
        self.assertEqual(agent.run(client, '你好'), '你好')
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_multiple_calls(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response(calls=[call(), call(id='second')]), response('完成')]
        agent.run(client, '计算')
        messages = client.chat.completions.create.call_args.kwargs['messages']
        self.assertEqual([m['tool_call_id'] for m in messages if m['role'] == 'tool'], ['call_1', 'second'])

    def test_limit_does_not_execute_last_tool(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response(calls=[call()])
        with patch.object(agent.agent_config, 'max_steps', 2), patch.object(agent, 'add', return_value=485) as add:
            with self.assertRaisesRegex(ValueError, '最大'):
                agent.run(client, '计算')
            self.assertEqual(client.chat.completions.create.call_count, 2)
            self.assertEqual(add.call_count, 1)

    def test_invalid_batch_is_not_executed(self):
        for bad in (call(name='bad'), call(arguments='{}'), call(arguments='invalid'), call()):
            with self.subTest(bad=bad), patch.object(agent, 'add') as add:
                client = MagicMock()
                client.chat.completions.create.return_value = response(calls=[call(), bad])
                with self.assertRaises(ValueError):
                    agent.run(client, '计算')
                add.assert_not_called()

    def test_tool_failure_stops(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response(calls=[call()])
        with patch.object(agent, 'add', side_effect=RuntimeError('test')):
            with self.assertRaisesRegex(ValueError, '执行失败'):
                agent.run(client, '计算')
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_model_failure_not_retried(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError('model failure')
        with self.assertRaises(RuntimeError):
            agent.run(client, '你好')
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_empty_and_truncated(self):
        for reply in (response(''), response('partial')):
            if reply.choices[0].message.content:
                reply.choices[0].finish_reason = 'length'
            client = MagicMock()
            client.chat.completions.create.return_value = reply
            with self.assertRaises(ValueError):
                agent.run(client, '你好')
