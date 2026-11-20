"""Independent payoff checks and end-to-end controls for the versioned design."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction as F
import json
import math
from pathlib import Path
import tempfile
import unittest

from gut.canonical import EXAMPLES, controlled_conditions, controlled_matrix
from gut import experiment as study
from gut import lab_experiment as lab
from gut import oversight_experiment as oversight
from gut.oversight import Oversight
from gut.oversight_report import summarize as oversight_summary
from gut.proofs import export_proofs
from prepare_threshold_studies import prepare

MODEL = {"id": "synthetic/demo", "provider": "local", "returned_provider": "local",
         "accepted_models": ["synthetic/demo"], "context_length": 1000,
         "prompt_price": "0", "completion_price": "0", "request_price": "0"}


class ControlledThresholdTests(unittest.TestCase):
    def test_exact_schedule_brackets_relevant_ties(self):
        counts = {"pd": 18, "stag_hunt": 12, "chicken": 12, "battle_of_sexes": 36}
        for key, count in counts.items():
            cells = controlled_conditions(key)
            self.assertEqual(len(cells), count)
            for target in {c['cost_action'] for c in cells}:
                primary = [c for c in cells if c['purpose'] == 'primary' and c['cost_action'] == target]
                costs = {F(c['z']) for c in primary}
                roots = {((1 if target == 1 else -1)*t) for role in ('row', 'column')
                         for t in EXAMPLES[key].thresholds(role) if (t >= 0 if target == 1 else t <= 0)}
                for root in roots:
                    self.assertIn(root, costs)
                    self.assertTrue(any(z < root for z in costs))
                    self.assertTrue(any(z > root for z in costs))
                if key in ('stag_hunt', 'chicken'):
                    self.assertNotIn(F(1), costs)

    def test_cost_and_affine_controls_apply_to_every_final_payoff(self):
        for key, spec in EXAMPLES.items():
            for cell in controlled_conditions(key):
                z, a, b = (F(cell[k]) for k in ('z', 'scale', 'offset'))
                table = controlled_matrix(key, cell)
                for i in (0, 1):
                    for j in (0, 1):
                        for p in (0, 1):
                            expected = a*(spec.baseline[i][j][p] - z*((i, j)[p] == cell['cost_action'])) + b
                            self.assertEqual(table[i][j][p], expected)
                for role in ('row', 'column'):
                    own = controlled_matrix(key, cell, role)
                    baseline = spec.margins(role)
                    for j in (0, 1):
                        expected = a*(baseline[j] + (z if cell['cost_action'] == 1 else -z))
                        self.assertEqual(own[0][j][0]-own[1][j][0], expected)

    def test_bos_mirror_preserves_roles_and_reverses_intervention(self):
        for target in (0, 1):
            cell = {'z': '9/4', 'cost_action': target, 'scale': '1', 'offset': '0'}
            for role in ('row', 'column'):
                own = controlled_matrix('battle_of_sexes', cell, role)
                for j in (0, 1):
                    self.assertGreater(own[1-target][j][0], own[target][j][0])
        # At the mirrored ties, row/column thresholds are swapped, not pooled.
        for role, z in (('row', '2'), ('column', '1')):
            own = controlled_matrix('battle_of_sexes', {'z': z, 'cost_action': 0, 'scale': '1', 'offset': '0'}, role)
            self.assertEqual(own[0][0][0], own[1][0][0])

    def test_fully_crossed_labels_and_display_order(self):
        plan = study.make_plan(game='pd', version='v2', repetitions=1)
        counts = Counter((j['condition_id'], j['block'], j['role']) for j in plan['jobs'])
        self.assertTrue(all(n == 1 for n in counts.values()))
        for cell in plan['conditions']:
            texts = [study.prompt(cell['z'], 'row', b, 'pd', cell) for b in range(4)]
            self.assertEqual(len(set(texts)), 4)
            for b in (0, 2):
                self.assertEqual(texts[b].splitlines()[2:6], texts[b+1].splitlines()[2:6][::-1])

    def test_raw_choices_summary_and_proofs_use_same_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/'bos'
            plan = study.save_plan(directory, game='battle_of_sexes', version='v2', repetitions=1)
            def fixed(job, plan):
                # Choose X in every block, treatment and representation.
                return 200, json.dumps({'model': plan['model'], 'choices': [{'finish_reason': 'stop', 'message': {
                    'content': json.dumps({'final_action': study.job_labels(plan, job)[0]})}}]}), None
            study.collect(directory, transport=fixed)
            rows = study.summarize(directory)['cells']
            self.assertEqual(len(rows), 36)
            self.assertTrue(all(r['XX'] == 4 and r['first_action_rate'] == 1 for r in rows))
            self.assertTrue(all(r['cooperation_rate'] is None for r in rows))
            export_proofs(directory)
            mapping = json.loads((directory/'proofs/mapping.json').read_text())
            jobs = {j['id']: j for j in plan['jobs']}
            for record in mapping:
                table = study.job_table(plan, jobs[record['id']])
                self.assertEqual([F(v, record['denominator']) for v in record['payoff_integers']],
                                 [table[i][j][0] for i in (0, 1) for j in (0, 1)])

    def test_four_block_bounds_and_missing_control_cells(self):
        mean, low, high = study.bounds([[1]*10, [0]*10, [1]*10, [0]*10])
        self.assertEqual(mean, .5)
        self.assertAlmostEqual(high-mean, math.sqrt(math.log(40)/80))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/'run'
            plan = study.save_plan(directory, version='v2', repetitions=1)
            rows = study.summarize(directory)['cells']
            self.assertEqual(len(rows), 18)
            self.assertTrue(all(r['first_action_rate'] is None and r['missing_upper'] == 1 for r in rows))
            altered = deepcopy(plan); altered['conditions'][0]['scale'] = '20'
            altered['sha256'] = study.digest({k: v for k, v in altered.items() if k != 'sha256'})
            (directory/'plan.json').write_text(json.dumps(altered))
            with self.assertRaises(ValueError):
                study.load_run(directory)

    def test_oversight_fixed_payoffs_and_exact_attack_cost_tie(self):
        defense = oversight.controlled_conditions('defense', 1)
        self.assertEqual(len(defense), 11)
        self.assertEqual(len({tuple(c['parameters'].items()) for c in defense}), 1)
        costs = oversight.controlled_conditions('attack_cost', 1)
        self.assertEqual({c['d'] for c in costs}, {'3/10'})
        self.assertEqual([Oversight(**c['parameters']).margin(c['d']) for c in costs],
                         [F(-1, 10), F(-1, 20), F(0), F(1, 20), F(1, 10)])

    def test_retired_resource_design_cannot_be_prepared(self):
        with self.assertRaises(ValueError):
            oversight.make_plan([MODEL], '1', mode='synthetic', design='resource')
        with self.assertRaises(ValueError):
            oversight.controlled_conditions('resource', 1)

    def test_new_sequential_plans_collect_and_reanalyze_without_pooling(self):
        with tempfile.TemporaryDirectory() as tmp:
            for design, n in (('defense', 11), ('attack_cost', 5)):
                directory = Path(tmp)/design
                plan = oversight.save_plan(directory, models=[MODEL], budget_usd='1', mode='synthetic',
                                           primary_reps=1, framing_reps=1, design=design)
                self.assertEqual(len(plan['jobs']), 4*n+4)
                with self.assertRaises(ValueError):
                    oversight.collect(directory, stage='main')
                oversight.collect(directory, max_calls=4)
                oversight.collect(directory, stage='main', max_calls=4*n)
                loaded, rows = oversight.observations(directory)
                summary = oversight_summary(loaded, rows)
                self.assertEqual(len(summary['cells']), n)
                self.assertTrue(all(r['optimal_rate'] == 1 for r in summary['cells']))

    def test_notebook_v2_includes_first_crossing_and_controls(self):
        pilot, main = lab.make_plan(version='v2'), lab.make_plan(version='v2', scale='main')
        self.assertEqual(pilot['max_requests'], 88)
        self.assertEqual(main['max_requests'], 960)
        self.assertEqual({j['budget'] for j in pilot['calibration']}, {0, 1, 2, 3, 8})
        self.assertEqual({j['budget'] for j in main['evaluation']}, {1, 2, 3})
        summary = lab.validate_and_analyze(pilot, lab.run(pilot))
        self.assertEqual({r['budget'] for r in summary['cells']}, {1, 2, 3})
        # Exact reference: two witnesses in eight records, choose two uniformly.
        q = 1-F(math.comb(6, 2), math.comb(8, 2))
        self.assertEqual(q, F(13, 28))
        self.assertEqual(16*q-7, F(3, 7))

    def test_suite_is_offline_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/'suite'
            manifest = prepare(directory, repetitions=1)
            self.assertEqual(manifest['live_model_calls'], 0)
            self.assertEqual({s['study'] for s in manifest['studies']}, set(EXAMPLES))
            self.assertFalse(list(directory.rglob('records*')))
            self.assertTrue(all((directory/e['plan']).is_file() for e in manifest['studies']))
            with self.assertRaises(FileExistsError):
                prepare(directory)


if __name__ == '__main__':
    unittest.main()
