"""No network or paid model calls. Test real Inspect logs and crash accounting."""
from copy import deepcopy
from decimal import Decimal as D
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

if importlib.util.find_spec('inspect_ai'):
    from gut import inspect_study as S

SPEC = {'id': 'openai/test-model', 'provider': 'openai', 'provider_name': 'OpenAI',
        'accepted_response_models': ['openai/test-model'], 'context_length': 10000,
        'max_completion_tokens': 2000, 'prompt_price': '0.000001',
        'completion_price': '0.000002', 'request_price': '0', 'source_url': 'public-test-fixture'}


@unittest.skipUnless(importlib.util.find_spec('inspect_ai'), 'Install inspect extra')
class InspectStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)/'study'

    def plan(self, **kwargs):
        return S.prepare(self.directory, ['audit_information'], repetitions=1, budget_usd='1', **kwargs)

    def test_immutable_manifest_and_no_multidimensional_sweep(self):
        plan = self.plan()
        self.assertEqual({j['metadata']['planned_q'] for j in plan['jobs']}, {None})
        self.assertEqual({j['metadata']['information'] for j in plan['jobs']}, {'revealed','hidden'})
        self.assertEqual({j['metadata']['presentation_block'] for j in plan['jobs']}, set(range(9)))
        for stage in ('pilot','main'):
            pairs = {}
            for job in plan['jobs']:
                if job['stage'] == stage:
                    pairs.setdefault(job['metadata']['pair_id'], []).append(job)
            self.assertEqual(len(pairs), 18)
            self.assertTrue(all(len(pair)==2 for pair in pairs.values()))
        changed = deepcopy(plan)
        changed['budget_usd'] = '2'
        (self.directory/'plan.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            S.load_plan(self.directory)

    def test_budget_reserves_all_roles_and_unknown_cost_is_not_refunded(self):
        plan = self.plan()
        plan['budget_usd'] = '.04'
        plan['sha256'] = S.digest({k:v for k,v in plan.items() if k != 'sha256'})
        ledger = S.Ledger(self.directory, plan)
        a,b,c = plan['jobs'][:3]
        self.assertTrue(ledger.start(a))
        with self.assertRaisesRegex(ValueError, 'never'):
            ledger.start(a)
        self.assertTrue(ledger.start(b))
        self.assertFalse(ledger.start(c))
        ledger.write(a, 'finish', {'status':'interrupted','actual_cost_usd':None,
                     'needs_review':True,'budget_breach':False})
        self.assertEqual(ledger.committed,D('.04'))
        ledger.write(b, 'finish', {'status':'invalid','actual_cost_usd':'.003',
                     'needs_review':False,'budget_breach':False})
        self.assertEqual(ledger.committed,D('.023'))
        self.assertFalse(ledger.start(c))
        loaded=S.Ledger(self.directory,plan)
        self.assertEqual(loaded.committed,ledger.committed)
        self.assertEqual(loaded.blockers,[a['id']])

    def test_native_roundtrip_restart_never_duplicates_and_export_keeps_missing(self):
        self.plan()
        with self.assertRaisesRegex(ValueError,'pilot'):
            S.run(self.directory,stage='main',max_trials=1)
        first=S.run(self.directory,stage='pilot',max_trials=2)
        self.assertEqual(first['valid'],2)
        self.assertEqual(first['cost_plus_reservations_usd'],'0')
        before={p: p.read_bytes() for p in (self.directory/'attempts').rglob('*.json')}
        second=S.run(self.directory,stage='pilot',max_trials=1)
        self.assertEqual(second['valid'],3)
        self.assertEqual(second['attempted_now'],1)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(),content)
        out=Path(self.tmp.name)/'export'
        S.export(self.directory,out)
        rows=[json.loads(l) for l in (out/'observations.jsonl').read_text().splitlines()]
        self.assertEqual(sum(r['status']=='valid' for r in rows),3)
        self.assertEqual(sum(r['status']=='not_started' for r in rows),len(rows)-3)
        self.assertTrue(all(r['native_log'] for r in rows if r['status']=='valid'))

    def test_crash_after_completed_eval_is_recovered_without_replay(self):
        plan=self.plan()
        original=S.Ledger.write
        def crash(ledger,job,kind,data):
            if kind=='finish':
                raise KeyboardInterrupt('simulated crash after native log was flushed')
            return original(ledger,job,kind,data)
        with patch.object(S.Ledger,'write',crash):
            with self.assertRaises(KeyboardInterrupt):
                S.run(self.directory,stage='pilot',max_trials=1)
        ledger=S.Ledger(self.directory,plan)
        self.assertEqual(len(ledger.starts),1)
        old=next(iter(ledger.starts))
        result=S.run(self.directory,stage='pilot',max_trials=1)
        self.assertEqual(result['valid'],2)
        self.assertEqual(result['attempted_now'],1)
        self.assertEqual(len(list((self.directory/'logs'/old).glob('*.eval'))),1)

    def test_ambiguous_attempt_requires_review_and_retains_reservation(self):
        plan=self.plan()
        ledger=S.Ledger(self.directory,plan)
        job=next(j for j in plan['jobs'] if j['stage']=='pilot')
        ledger.start(job)  # simulate a crash after durable reserve, before response
        with self.assertRaisesRegex(ValueError,'review'):
            S.run(self.directory,stage='pilot',max_trials=1)
        S.review(self.directory,job['id'],'Reviewed the interrupted trial; preserve its full charge reservation.')
        result=S.run(self.directory,stage='pilot',max_trials=1)
        self.assertEqual(result['cost_plus_reservations_usd'],'0.02')
        self.assertEqual(result['attempted'],2)
        self.assertFalse((self.directory/'logs'/job['id']).exists())

    def test_lock_atomicity_and_code_changes_fail_closed(self):
        self.plan()
        with S.study_lock(self.directory):
            with self.assertRaisesRegex(ValueError,'owns'):
                with S.study_lock(self.directory):
                    self.fail('second collector acquired lock')
        marker=self.directory/'marker.json'
        S.atomic_json(marker,{'keep':1})
        with self.assertRaises(FileExistsError):
            S.atomic_json(marker,{'keep':2})
        self.assertEqual(S.read_json(marker),{'keep':1})
        with patch.object(S,'provenance',return_value={}):
            with self.assertRaisesRegex(ValueError,'dependencies changed'):
                S.run(self.directory,stage='pilot',max_trials=1)

    def test_reject_corrupted_ledger_and_native_log(self):
        plan=self.plan()
        S.run(self.directory,stage='pilot',max_trials=1)
        path=next((self.directory/'attempts').glob('*/finish.json'))
        original=path.read_text()
        data=json.loads(original); data['actual_cost_usd']='-1'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'record changed'):
            S.Ledger(self.directory,plan)
        path.write_text(original)
        native=self.directory/data['native_log']
        with native.open('ab') as out: out.write(b'altered')
        with self.assertRaisesRegex(ValueError,'Native log'):
            S.Ledger(self.directory,plan)

    def test_provider_boundaries_and_raw_usage_reconciliation(self):
        plan=self.plan()
        plan['mode']='openrouter';plan['models']=[SPEC]
        job=plan['jobs'][0]
        metadata={'study_sha256':plan['sha256'],'job_id':job['id']}
        def event(role,cost='.001',**updates):
            raw={'model':SPEC['id'],'provider':'OpenAI','usage':{'cost':cost}}
            raw.update(updates)
            return NS(event='model',role=role,retries=0,cache=None,model='openrouter/'+SPEC['id'],
                      call=NS(response=raw),error=None)
        sample=NS(id=job['sample_id'],error=None,metadata={'record':{'status':'valid'}},
                  events=[event(r) for r in job['roles']])
        log=NS(samples=[sample],status='success',eval=NS(metadata=metadata))
        result=S.assess_log(plan,job,log)
        self.assertEqual(result['actual_cost_usd'],'0.002')
        self.assertFalse(result['needs_review'])
        sample.events[0].call.response['usage']={}
        result=S.assess_log(plan,job,log)
        self.assertIsNone(result['actual_cost_usd'])
        self.assertTrue(result['needs_review'])
        sample.events=[event(r,cost='2') for r in job['roles']]
        self.assertTrue(S.assess_log(plan,job,log)['budget_breach'])
        sample.events=[event(r,provider='unexpected') for r in job['roles']]
        self.assertTrue(S.assess_log(plan,job,log)['needs_review'])
        options=S.provider_options(SPEC)
        self.assertEqual(options['only'],['openai'])
        self.assertFalse(options['allow_fallbacks'])
        self.assertEqual(options['max_price'],{'prompt':1.0,'completion':2.0,'request':0.0})

    def test_real_openrouter_adapter_with_fake_sdk_no_network(self):
        # Exercise actual SDK request construction + native raw-cost logs.
        from openai.types.chat import ChatCompletion
        from inspect_ai.model._providers.openrouter import OpenRouterAPI
        requests=[]
        async def completion(api,request,config):
            requests.append(request)
            prompt=request['messages'][0]['content']
            content='{"q":"1/2"}' if 'You are the defender.' in prompt else '{"action":"A"}'
            return ChatCompletion.model_validate({'id':'test-only','object':'chat.completion','created':0,
                'model':SPEC['id'],'provider':'OpenAI',
                'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':content}}],
                'usage':{'prompt_tokens':40,'completion_tokens':10,'total_tokens':50,'cost':.001}})
        with patch.object(S,'endpoint_spec',return_value=SPEC), patch.dict(os.environ,{'OPENROUTER_API_KEY':'test-placeholder'}):
            plan=self.plan(mode='openrouter',models=[{'id':SPEC['id'],'provider':'openai'}],
                           model_settings={SPEC['id']:{'reasoning_enabled':False}})
            with self.assertRaisesRegex(ValueError,'requires --live'):
                S.run(self.directory,stage='pilot',max_trials=1)
            with patch.object(OpenRouterAPI,'_generate_completion',completion):
                result=S.run(self.directory,stage='pilot',max_trials=1,live=True)
        self.assertEqual(result['valid'],1)
        self.assertEqual(result['cost_plus_reservations_usd'],'0.002')
        self.assertEqual(len(requests),2)
        for request in requests:
            self.assertEqual(request['max_tokens'],512)
            self.assertEqual(request['extra_body']['provider'],S.provider_options(SPEC))
            self.assertEqual(request['extra_body']['reasoning'],{'enabled':False})

    def test_live_endpoint_drift_stops_before_any_reservation(self):
        with patch.object(S,'endpoint_spec',return_value=SPEC):
            self.plan(mode='openrouter',models=[{'id':SPEC['id'],'provider':'openai'}])
        with patch.object(S,'endpoint_spec',return_value={**SPEC,'context_length':20000}), patch.dict(
                os.environ,{'OPENROUTER_API_KEY':'test-placeholder'}):
            with self.assertRaisesRegex(ValueError,'Endpoint prices'):
                S.run(self.directory,stage='pilot',max_trials=1,live=True)
        self.assertEqual(S.status(self.directory)['attempted'],0)

    def test_invalid_money_and_cross_mode(self):
        for value in ('NaN','Infinity','-1','bad',True):
            with self.assertRaises(ValueError):
                S.money(value)
        self.plan()
        with self.assertRaisesRegex(ValueError,'omit'):
            S.run(self.directory,stage='pilot',max_trials=1,live=True)

    def test_no_implicit_routing_or_search_surcharges(self):
        with patch.object(S.urllib.request, 'urlopen') as network:
            for model in ('openrouter/auto', 'openai/test:online', 'openai/test:free'):
                with self.assertRaises(ValueError):
                    S.endpoint_spec(model, 'openai')
            network.assert_not_called()
