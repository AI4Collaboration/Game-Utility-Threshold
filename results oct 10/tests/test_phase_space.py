import json
import asyncio
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from utility_threshold.games.phase_space import SymmetricPayoffs, phase_grid, axis_values, score_joint
from run_phase_space import MODELS, cases, parse_decision, prompt_for, request_for, reservation, run


class PhaseSpaceTests(unittest.TestCase):
    def test_original_normalizes_and_affine_invariance(self):
        base=SymmetricPayoffs()
        self.assertEqual((base.s,base.t),(-.5,2))
        for scale,shift in [(2,1),(10,0),(1,10),(.01,-5)]:
            altered=base.affine(scale,shift)
            self.assertAlmostEqual(altered.s,base.s)
            self.assertAlmostEqual(altered.t,base.t)
            self.assertEqual(altered.game().pure_nash_equilibria(),base.game().pure_nash_equilibria())

    def test_all_twelve_strict_orders_and_four_regimes(self):
        points=phase_grid(axis_values())
        orders={p.report()['payoff_order'] for p in points if '=' not in p.report()['payoff_order']}
        self.assertEqual(len(orders),12)
        self.assertEqual({p.regime for p in points},
                         {'boundary','C_dominant','D_dominant','coordination','anti_coordination'})

    def test_equilibrium_formula_and_boundary_ties(self):
        for s,t in [(-.5,.5),(.5,1.5),(-1,.25),(.25,2)]:
            p=SymmetricPayoffs(T=t,R=1,P=0,S=s)
            mixed=p.report()['mixed_cooperation_probability']
            self.assertAlmostEqual(mixed,-s/(1-t-s))
            self.assertAlmostEqual(p.margin(mixed),0)
        p=SymmetricPayoffs(T=1,R=1,P=0,S=0)
        self.assertEqual(len(p.game().pure_nash_equilibria()),4)
        self.assertEqual(p.regime,'boundary')

    def test_pd_not_always_socially_cc_optimal(self):
        p=SymmetricPayoffs(T=4,R=1,P=0,S=-.5)
        self.assertTrue(p.report()['strict_pd'])
        self.assertFalse(p.report()['mutual_cooperation_socially_optimal'])
        self.assertEqual(set(p.game().welfare_optimal_profiles()),{('C','D'),('D','C')})

    def test_invalid_actions_never_scored_as_real_outcomes(self):
        self.assertEqual(score_joint(SymmetricPayoffs(),None,'D'),{'valid':False})
        score=score_joint(SymmetricPayoffs(),'D','D')
        self.assertTrue(score['nash'])
        self.assertFalse(score['pareto'])

    def test_strict_parser_and_counterbalancing(self):
        case=cases('pilot',0)[0]
        _,mapping=prompt_for(case,'row')
        d=parse_decision(json.dumps({'final_action':'A','belief_opponent_A':.8,'confidence':.9}),mapping)
        self.assertEqual(d['action'],'C')
        _,inverse=prompt_for({**case,'replicate':1},'row')
        d=parse_decision(json.dumps({'final_action':'A','belief_opponent_A':.8,'confidence':.9}),inverse)
        self.assertEqual(d['action'],'D')
        self.assertAlmostEqual(d['belief_opponent_C'],.2)
        self.assertFalse(parse_decision('I considered A then B',mapping)['valid'])
        self.assertFalse(parse_decision('[]',mapping)['valid'])

    def test_reservation_includes_all_output_and_max_price(self):
        job={'case':cases('pilot',0)[0],'role':'row','model':'test','job_id':'test'}
        catalog={'pricing':{'prompt':.00001,'completion':.00005},'supported_parameters':[]}
        payload,_=request_for(job,catalog,1024)
        self.assertGreater(reservation(payload,catalog['pricing']),1024*.00005)
        self.assertEqual(payload['provider']['max_price'],{'prompt':10,'completion':50})
        self.assertNotIn('temperature',payload)
        self.assertNotIn('seed',payload)

    def test_perspective_control_preserves_own_payoffs_in_both_roles(self):
        samples=cases('perspective',0)
        self.assertEqual(len(samples),20)
        case=next(c for c in samples if c['payoffs']['s']==-.5 and c['payoffs']['t']==2)
        for role in ('row','column'):
            prompt,_=prompt_for(case,role)
            self.assertIn('your action=A, opponent action=B: (your payoff -0.5, opponent payoff 2)',prompt)
            self.assertIn('your action=B, opponent action=A: (your payoff 2, opponent payoff -0.5)',prompt)
        row,_=prompt_for(case,'row');col,_=prompt_for(case,'column')
        self.assertEqual(row.replace('the row player','the column player'),col)

    def test_budget_waits_for_settlement_and_resumes_without_duplicate_calls(self):
        class FakeClient:
            calls=0
            active=0
            peak=0
            def __init__(self,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def post(self,url,json):
                FakeClient.calls+=1;FakeClient.active+=1
                FakeClient.peak=max(FakeClient.peak,FakeClient.active)
                await asyncio.sleep(.005)
                FakeClient.active-=1
                body={'model':json['model'],'provider':'mock','usage':{'cost':.000001},
                      'choices':[{'finish_reason':'stop','message':{'content':
                          '{"final_action":"A","belief_opponent_A":0.5,"confidence":0.5}'}}]}
                return SimpleNamespace(status_code=200,json=lambda:body)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);catalog=root/'models.json'
            catalog.write_text(json.dumps({'data':[{'id':mid,'pricing':{'prompt':1e-8,'completion':1e-8},
                                                   'supported_parameters':[]} for mid in MODELS.values()]}))
            args=SimpleNamespace(output=str(root/'run'),catalog=str(catalog),stage='pilot',
                                 replicate=0,models=['glm'],budget=.00008,max_tokens=4096,
                                 concurrency=4,limit=4)
            with patch('run_phase_space.httpx.AsyncClient',FakeClient), \
                 patch.dict('os.environ',{'OPENROUTER_API_KEY':'offline-test-key'}), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(asyncio.run(run(args)),0)
                self.assertEqual(FakeClient.calls,4)
                self.assertEqual(FakeClient.peak,1)
                args.limit=None
                self.assertEqual(asyncio.run(run(args)),0)
                self.assertEqual(FakeClient.calls,8)
                self.assertEqual(asyncio.run(run(args)),0)
                self.assertEqual(FakeClient.calls,8)
            ledger=json.loads((root/'run/ledger.json').read_text())
            self.assertAlmostEqual(ledger['reported_usd'],.000008)
            self.assertLessEqual(ledger['accounted_usd'],ledger['cap_usd'])
            self.assertFalse(ledger['reservations'])


if __name__=='__main__':
    unittest.main()
