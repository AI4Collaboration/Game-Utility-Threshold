from collections import Counter
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from gut import experiment as canonical
from gut import threshold_validation as suite
from gut import oversight_experiment as sequential
from gut.canonical import EXAMPLES


MODEL = {'id': 'test/model', 'provider': 'test', 'returned_provider': 'Test',
         'accepted_models': ['test/model', 'test/model-version'], 'context_length': 1000,
         'prompt_price': '.00001', 'completion_price': '0', 'request_price': '0'}


def response(job, plan):
    return 200, json.dumps({'model': 'test/model-version', 'provider': 'Test', 'usage': {'cost': .001},
             'choices': [{'finish_reason': 'stop', 'message': {'content': '{"final_action":"A"}'}}]}), None


class SharedValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'suite'

    def prepare(self, budget='1'):
        return suite.prepare(self.path, [MODEL], budget_usd=budget, repetitions=2,
                             control_repetitions=1)

    def test_new_live_suite_contains_only_established_games(self):
        plan = self.prepare()
        self.assertEqual({s['family'] for s in plan['studies']}, {'canonical'})
        self.assertEqual({s['name'] for s in plan['studies']}, {f'{g}-m0' for g in EXAMPLES})
        self.assertEqual(len(plan['studies']), 4)
        self.assertFalse((self.path/'ledger.jsonl').exists())

    def test_historical_mixed_suite_can_be_read_but_not_collected(self):
        plan = self.prepare()
        old = sequential.save_plan(self.path/'oversight', models=[MODEL], budget_usd='1',
                                   mode='openrouter', primary_reps=1, framing_reps=1)
        studies = plan['studies'] + [{'name': 'oversight', 'family': 'sequential', 'sha256': old['sha256']}]
        mixed, _ = suite.construct(self.path, studies, '1', plan['seed'])
        manifest = self.path/'manifest.json'
        manifest.write_text(json.dumps(mixed))
        original = manifest.read_bytes()
        self.assertEqual(suite.read_ledger(self.path)[0], mixed)
        transport = Mock()
        with patch('gut.oversight_experiment.local_key') as key:
            for override in (None, transport):
                with self.assertRaisesRegex(ValueError, 'unapproved custom prototype'):
                    suite.collect(self.path, 'pilot', live=True, transport=override)
            key.assert_not_called()
        transport.assert_not_called()
        self.assertEqual(manifest.read_bytes(), original)
        self.assertFalse((self.path/'ledger.jsonl').exists())
        self.assertFalse((self.path/'.collect.lock').exists())

    def test_smaller_controls_balance_every_role_and_block(self):
        plan = canonical.make_plan(version='v2', repetitions=10, control_repetitions=3)
        for cell in plan['conditions']:
            counts = Counter((j['block'], j['role']) for j in plan['jobs'] if j['condition_id'] == cell['id'])
            self.assertEqual(set(counts.values()), {10 if cell['purpose'] == 'primary' else 3})
            self.assertEqual(len(counts), 8)

    def test_aliases_accepted_but_provider_mismatch_rejected(self):
        plan = canonical.make_plan(version='v2', mode='openrouter', model='test/model', provider='test', model_spec=MODEL)
        job = plan['jobs'][0]
        status, body, error = response(job, plan)
        finish = {'http_status': status, 'body': body, 'error': error}
        self.assertEqual(canonical.decision(plan, job, finish)[1], 'valid')
        wrong = json.loads(body); wrong['provider'] = 'Other'
        self.assertEqual(canonical.decision(plan, job, {**finish, 'body': json.dumps(wrong)})[1], 'provider_mismatch')

    def test_gate_resume_and_native_projection_preserve_observations(self):
        plan = self.prepare()
        with self.assertRaises(ValueError):
            suite.collect(self.path, 'main', live=True, transport=response)
        pilots = sum(j['stage'] == 'pilot' for j in plan['jobs'])
        result = suite.collect(self.path, 'pilot', live=True, max_calls=pilots, transport=response)
        self.assertEqual(result['attempted_now'], pilots)
        self.assertEqual(suite.collect(self.path, 'pilot', live=True, transport=response)['attempted_now'], 0)
        suite.collect(self.path, 'main', live=True, max_calls=9, transport=response)
        suite.materialize(self.path)
        ledger = suite.read_ledger(self.path)
        self.assertEqual(len(ledger[2]), pilots+9)
        self.assertEqual(ledger[4], Decimal('.001')*(pilots+9))
        native_count = sum(len(canonical.load_run(self.path/s['name'])[1]) for s in plan['studies'] if s['family'] == 'canonical')
        expected = sum(j['stage'] == 'main' and j['study'].startswith(('pd-', 'stag_hunt-', 'chicken-', 'battle_of_sexes-'))
                       and j['id'] in ledger[2] for j in plan['jobs'])
        self.assertEqual(native_count, expected)

    def test_shared_cap_reserves_before_dispatch(self):
        self.prepare(budget='.01')
        def full_cost(job, plan):
            status, body, error = response(job, plan)
            body = json.loads(body); body['usage']['cost'] = .01
            return status, json.dumps(body), error
        result = suite.collect(self.path, 'pilot', live=True, workers=8, max_calls=100, transport=full_cost)
        self.assertEqual(result['attempted_now'], 1)
        self.assertEqual(result['stop'], 'budget_cap')

    def test_ambiguous_cost_stays_reserved_no_retry_after_audit(self):
        self.prepare()
        def failure(job, plan):
            return 0, '', 'TimeoutError'
        suite.collect(self.path, 'pilot', live=True, workers=1, transport=failure)
        plan, _, starts, _, cost = suite.read_ledger(self.path)
        self.assertEqual(cost, Decimal('.01'))
        jid = next(iter(starts))
        with self.assertRaises(ValueError):
            suite.collect(self.path, 'pilot', live=True, transport=response)
        suite.audit(self.path, jid, 'Inspected timeout; unknown cost remains reserved; never retry.')
        suite.collect(self.path, 'pilot', live=True, max_calls=1, transport=response)
        _, _, starts, finishes, cost = suite.read_ledger(self.path)
        self.assertEqual(len(starts), 2)
        self.assertEqual(finishes[jid]['http_status'], 0)
        self.assertEqual(cost, Decimal('.011'))

    def test_changed_prompt_and_duplicate_ledger_fail_closed(self):
        self.prepare()
        suite.collect(self.path, 'pilot', live=True, max_calls=1, transport=response)
        path = self.path/'ledger.jsonl'
        original = path.read_text()
        path.write_text(original+original.splitlines()[0]+'\n')
        with self.assertRaises(ValueError):
            suite.read_ledger(self.path)
        path.write_text(original)
        child = self.path/'pd-m0'/'plan.json'
        plan = json.loads(child.read_text())
        plan['jobs'][0]['request']['messages'][0]['content'] = 'altered'
        child.write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            suite.read_ledger(self.path)


if __name__ == '__main__':
    unittest.main()
