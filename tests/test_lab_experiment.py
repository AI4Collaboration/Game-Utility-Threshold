"""Frozen schedules, honest uncertainty, raw-response auditing and failure paths."""
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gut import lab_experiment as study


class StudyTests(unittest.TestCase):
    def test_scope_balanced_blocks_and_separate_notebooks(self):
        pilot=study.make_plan();main=study.make_plan(scale='main')
        self.assertEqual(pilot['max_requests'],80)
        self.assertEqual(main['max_requests'],960)
        self.assertEqual(len(main['calibration']),480)
        self.assertEqual(len(main['evaluation']),240)
        self.assertEqual(len(main['cases']),720)
        cal={j['case_id'] for j in main['calibration']};ev={j['case_id'] for j in main['evaluation']}
        self.assertFalse(cal & ev)
        for k in (1,3,6):
            for report in ('compliant','selective'):
                for block in range(4):
                    self.assertEqual(sum(j['budget']==k and j['report']==report and j['block']==block for j in main['calibration']),20)
        changed=deepcopy(pilot);changed['calibration'].pop()
        with self.assertRaises(ValueError):study.verify_plan(changed)
        self.assertNotEqual(study.make_plan(seed=1)['sha256'],pilot['sha256'])

    def test_deterministic_roundtrip_baselines_and_scores(self):
        for reviewer in study.REVIEWERS:
            plan=study.make_plan(reviewer=reviewer)
            run=study.run(plan)
            self.assertEqual(run,study.run(plan))
            summary=study.validate_and_analyze(plan,run)
            self.assertEqual(summary['live_model_calls'],0)
            self.assertEqual(summary['recorded_requests'],80)
            self.assertEqual(len(summary['cells']),6)
            for row in summary['cells']:
                self.assertEqual(row['optimal_count'],row['valid'])
                margin=float(F(row['forecast']['margin']))
                self.assertLessEqual(row['margin_lower'],margin)
                self.assertGreaterEqual(row['margin_upper'],margin)
        for scientist,expected in [('always_compliant','0'),('always_selective','1')]:
            plan=study.make_plan(scientist=scientist)
            summary=study.validate_and_analyze(plan,study.run(plan))
            self.assertTrue(all(r['selective_rate']['estimate']==expected for r in summary['cells']))

    def test_invalid_scientist_never_gets_a_fabricated_report(self):
        plan=study.make_plan()
        result=study.run(plan,scientist_actor=lambda *args:'not JSON')
        summary=study.validate_and_analyze(plan,result)
        self.assertEqual(summary['recorded_requests'],56)
        for row in summary['cells']:
            self.assertEqual(row['valid'],0)
            self.assertIsNone(row['selective_rate']['estimate'])
            self.assertIsNone(row['mean_human'])
            self.assertEqual(row['selective_rate']['lower'],0)
            self.assertEqual(row['selective_rate']['upper'],1)
        self.assertTrue(all(r['reviewer'] is None for r in result['evaluation']))

    def test_invalid_reviewer_fail_closed_is_explicit_and_counted(self):
        plan=study.make_plan()
        result=study.run(plan,reviewer_actor=lambda *args:'not JSON')
        summary=study.validate_and_analyze(plan,result)
        for row in summary['calibration'].values():
            for key in ('detection','false_return'):
                self.assertEqual(row[key]['estimate'],'1')
                self.assertEqual(row[key]['invalid'],row[key]['planned'])
        self.assertTrue(all(r['verdict']=='return' and r['reviewer_status']=='invalid_answer' for r in summary['observations']))

    def test_tampered_requests_rates_duplicates_and_missing_jobs_rejected(self):
        plan=study.make_plan();result=study.run(plan)
        for mutate in (
            lambda r:r['calibration'][0]['response'].update(prompt='leaked notebook'),
            lambda r:r['calibrated_rates']['1']['detection'].update(estimate='0'),
            lambda r:r['evaluation'][0].update(calibration_sha256='wrong'),
            lambda r:r['evaluation'].pop(),
            lambda r:r['evaluation'].__setitem__(0,r['evaluation'][1]),
            lambda r:r['calibration'][0]['response'].update(synthetic=False),
        ):
            changed=deepcopy(result);mutate(changed)
            with self.assertRaises(ValueError):study.validate_and_analyze(plan,changed)

    def test_saved_report_and_rate_bounds(self):
        plan=study.make_plan();result=study.run(plan)
        with TemporaryDirectory() as tmp:
            summary=study.report(tmp,plan,result)
            self.assertIn('OFFLINE SYNTHETIC',Path(tmp,'report.html').read_text())
            self.assertTrue(Path(tmp,'cells.csv').is_file())
            self.assertEqual(summary['planned_max_requests'],80)
        narrow=study.bounded_rate(40,80,80)
        corrected=study.bounded_rate(40,80,80,comparisons=6)
        self.assertLess(corrected['lower'],narrow['lower'])
        self.assertGreater(corrected['upper'],narrow['upper'])
        missing=study.bounded_rate(20,40,80)
        self.assertLess(missing['lower'],narrow['lower'])
        self.assertGreater(missing['upper'],narrow['upper'])
        with self.assertRaises(ValueError):study.bounded_rate(5,4,8)

    def test_interval_margin_contains_interior_gain_and_rate_extremes(self):
        plan=study.make_plan(scale='main', reviewer='noisy_evidence')
        summary=study.validate_and_analyze(plan,study.run(plan))
        for bound in summary['gain_interval_margins']:
            rates=summary['calibration'][str(bound['budget'])]
            for gain in (4, 5, 6, 7, 8):
                for q in (rates['detection']['lower'], rates['detection']['upper']):
                    for f in (rates['false_return']['lower'], rates['false_return']['upper']):
                        margin=(gain+8)*q-(gain-1)-f
                        self.assertLessEqual(bound['margin_lower'],margin)
                        self.assertGreaterEqual(bound['margin_upper'],margin)


if __name__=='__main__':unittest.main()
