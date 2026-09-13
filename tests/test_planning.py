"""P2 的计划依赖、有限修正和执行边界。"""

import json
import unittest
from unittest.mock import MagicMock, patch

from test_tool_call import response
from hello_agent.schemas.planning import Plan
from hello_agent.sdk.p02_plan_execute import agent

PLAN = {"steps": [
    {"id": "first", "tool": "add", "a": 127, "b": 358},
    {"id": "second", "tool": "add", "a": {"step": "first"}, "b": 96},
]}


class PlanningTests(unittest.TestCase):
    def setUp(self):
        for key, value in (("max_steps", 5), ("max_repairs", 1)):
            p = patch.object(agent.planning_config, key, value)
            p.start()
            self.addCleanup(p.stop)

    def test_dependency_and_summary(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response(json.dumps(PLAN)), response('581')]
        self.assertEqual(agent.run(client, '计算'), '581')
        payload = json.loads(client.chat.completions.create.call_args.kwargs['messages'][-1]['content'])
        self.assertEqual([r['result'] for r in payload['results']], [485, 581])
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_repair_before_execution(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response('invalid'), response(json.dumps(PLAN)), response('581')]
        self.assertEqual(agent.run(client, '计算'), '581')
        self.assertEqual(client.chat.completions.create.call_count, 3)

    def test_invalid_never_executes(self):
        for content in ('bad json', '{"steps": [{"id":"a","tool":"bad","a":1,"b":2}]}',
                        '{"steps":[{"id":"a","tool":"add","a":{"step":"a"},"b":2}]}'):
            with self.subTest(content=content), patch.object(agent, 'add') as add:
                client = MagicMock()
                client.chat.completions.create.return_value = response(content)
                with self.assertRaises(ValueError):
                    agent.run(client, '计算')
                add.assert_not_called()
                self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_limit_before_execution(self):
        with patch.object(agent.planning_config, 'max_steps', 1), patch.object(agent, 'add') as add:
            client = MagicMock()
            client.chat.completions.create.return_value = response(json.dumps(PLAN))
            with self.assertRaises(ValueError):
                agent.run(client, '计算')
            add.assert_not_called()

    def test_empty_plan(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = [response('{"steps":[]}'), response('你好')]
        with patch.object(agent, 'add') as add:
            self.assertEqual(agent.run(client, '你好'), '你好')
            add.assert_not_called()

    def test_duplicate_and_forward_reference(self):
        for steps in (PLAN['steps'][::-1], [PLAN['steps'][0], PLAN['steps'][0]]):
            with self.assertRaises(ValueError):
                Plan.model_validate_json(json.dumps({'steps': steps}))

    def test_tool_failure_no_reexecution(self):
        client = MagicMock()
        client.chat.completions.create.return_value = response(json.dumps(PLAN))
        with patch.object(agent, 'add', side_effect=RuntimeError('failure')) as add:
            with self.assertRaisesRegex(ValueError, '工具执行失败'):
                agent.run(client, '计算')
            self.assertEqual(add.call_count, 1)
        self.assertEqual(client.chat.completions.create.call_count, 1)
