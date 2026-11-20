"""Offline handoff checks: native games, fixed counts, missingness and secret-free ZIP."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

AVAILABLE=importlib.util.find_spec('inspect_ai') is not None
if AVAILABLE:
    from gut import inspect_study as S, manager_study as M, manager_report as R
    from gut.canonical_inspect import canonical_samples, parse_action
    from gut.canonical import EXAMPLES, controlled_conditions


@unittest.skipUnless(AVAILABLE,'Install inspect extra')
class ManagerStudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)/'study'

    def test_canonical_conditions_and_balanced_labels_are_preserved(self):
        for game in EXAMPLES:
            samples=canonical_samples(game,5,2)
            for condition in controlled_conditions(game):
                rows=[s.metadata for s in samples if s.metadata['condition']==condition]
                count=5 if condition['purpose']=='primary' else 2
                self.assertEqual(len(rows),4*count)
                self.assertEqual({r['presentation_block'] for r in rows},set(range(4)))
            self.assertEqual(len(canonical_samples(game,pilot=True)),4)
        self.assertEqual(parse_action('{"final_action":"A"}',0),0)
        self.assertEqual(parse_action('{"final_action":"A"}',2),1)
        with self.assertRaises(ValueError):
            parse_action('{"final_action":"A","final_action":"B"}',0)

    def test_all_base_games_native_logs_and_exact_choices(self):
        plan=S.prepare(self.directory,list(EXAMPLES),repetitions=1,budget_usd='1')
        result=S.run(self.directory,stage='pilot',max_trials=100)
        self.assertEqual(result['valid'],16)
        ledger=S.Ledger(self.directory,plan)
        for job in plan['jobs']:
            if job['stage']!='pilot': continue
            record=ledger.finishes[job['id']]['record']
            for choice in record['choices'].values():
                self.assertFalse(choice['strict_dominance_violation'])
            if job['study']=='pd':
                expected='D' if record['cost']=='0' else 'C'
                self.assertEqual({c['action'] for c in record['choices'].values()},{expected})
        self.assertEqual(S.run(self.directory,stage='pilot',max_trials=1)['attempted_now'],0)

    def test_fixed_sample_counts_and_small_controls(self):
        config=M.configuration()
        plan=S.prepare(self.directory,list(config['repetitions_by_study']),mode='synthetic',
                       repetitions=config['repetitions'],control_repetitions=config['control_repetitions'],
                       repetitions_by_study=config['repetitions_by_study'],budget_usd=config['budget_usd'])
        main=[j for j in plan['jobs'] if j['stage']=='main']
        pilot=[j for j in plan['jobs'] if j['stage']=='pilot']
        self.assertEqual(sum(len(j['roles']) for j in main),5700)
        self.assertEqual(sum(len(j['roles']) for j in pilot),186)
        self.assertEqual(len(main),3192)
        self.assertEqual(len(pilot),102)
        self.assertEqual(set(plan['studies']),set(S.STUDIES))

    def test_balanced_estimates_and_missing_bounds(self):
        result=R.estimate({0:[1,1],1:[0,None]},0,1)
        self.assertEqual(result['mean'],.5)  # not 2/3 from naïve pooling
        self.assertEqual(result['missing_lower'],.5)
        self.assertEqual(result['missing_upper'],.75)
        self.assertEqual(result['valid'],3)
        self.assertIsNone(R.estimate({0:[1],1:[None]},0,1)['mean'])
        self.assertEqual(R.estimate({0:[None],1:[None]},0,1)['missing_upper'],1)

    def test_report_excludes_pilots_keeps_valid_individual_and_missing_pairs(self):
        plan=S.prepare(self.directory,['private_pd_v1'],repetitions=1,budget_usd='1')
        S.run(self.directory,stage='pilot',max_trials=1)
        out=Path(self.tmp.name)/'out'; S.export(self.directory,out)
        rows=[json.loads(l) for l in (out/'observations.jsonl').read_text().splitlines()]
        reference=next(r for r in rows if r['record'])
        target=next(r for r in rows if r['stage']=='main' and r['metadata']['information']=='hidden')
        target['record']=deepcopy(reference['record'])
        target['record']['choices']['row'].update(status='valid',action='C',strict_dominance_violation=False)
        target['record']['choices']['column']={'status':'invalid'}
        target['record']['status']='invalid'
        flat=R.flatten(rows); cells,_=R.summaries(flat)
        self.assertEqual(sum(c['valid'] for c in cells if c['metric']=='first_action_rate' and c['role']=='row'),1)
        self.assertEqual(sum(c['valid'] for c in cells if c['metric']=='first_action_rate' and c['role']=='column'),0)
        effects=R.paired_effects(flat)
        self.assertTrue(all(c['valid']==0 for c in effects))
        report=R.report(out,plan,figures=False)
        self.assertFalse(report['complete'])
        self.assertIn('SYNTHETIC SOFTWARE CHECK',(out/'report.html').read_text())

    def test_bundle_allowlist_nested_log_secret_check_and_checksums(self):
        self.directory.mkdir(); out=self.directory/'reports'/'one'; out.mkdir(parents=True)
        (self.directory/'plan.json').write_text('{}')
        (self.directory/'.env').write_text('OPENROUTER_API_KEY=must-not-be-shared')
        (out/'report.html').write_text('Results')
        archive=M.bundle(self.directory,out,self.directory/'results.zip')
        with zipfile.ZipFile(archive) as z:
            self.assertNotIn('study/.env',z.namelist())
            hashes=json.loads(z.read('SHA256.json'))
            self.assertEqual(hashes['results/report.html'],M.sha256(b'Results').hexdigest())
        log=self.directory/'logs'/'job';log.mkdir(parents=True)
        with zipfile.ZipFile(log/'fake.eval','w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('payload.json','sk-or-v1-'+'x'*32)
        with self.assertRaisesRegex(ValueError,'native log'):
            M.bundle(self.directory,out,self.directory/'bad.zip')
        self.assertFalse((self.directory/'bad.zip').exists())

    def test_one_command_smoke_resume_and_report_bundle(self):
        config=M.configuration()
        config['repetitions_by_study']={'pd':1,'audit_information':1}
        with patch.object(M,'configuration',return_value=config):
            plan=M.prepare(self.directory,smoke=True)
            result=S.run(self.directory,stage='pilot',max_trials=100)
            self.assertEqual(result['stop'],'complete')
            S.run(self.directory,stage='main',max_trials=100)
            self.assertEqual(M.prepare(self.directory,smoke=True)['sha256'],plan['sha256'])
            result=M.collect_results(self.directory,figures=False)
            self.assertTrue(result['complete'])
            self.assertTrue((self.directory/'results.zip').exists())
