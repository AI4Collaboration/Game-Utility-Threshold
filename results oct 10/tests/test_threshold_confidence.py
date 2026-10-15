import math
import unittest
from pathlib import Path

from scripts.report_threshold_confidence import (load_games,game_scores,bounded_tail,
    accepts_candidate,threshold_set,difference_set,analyze,summary_for)

ROOT=Path(__file__).resolve().parents[1]


class ThresholdConfidenceTests(unittest.TestCase):
    def test_bounded_tail_dominates_exact_binomial_tail(self):
        # An independent reference calculation checks the KL bound at the
        # least-favorable Bernoulli null. Games need not actually be Bernoulli.
        for n in range(1,25):
            for k in range(n//2+1):
                values=[1.]*k+[0.]*(n-k)
                exact=sum(math.comb(n,j) for j in range(k+1))/2**n
                self.assertGreaterEqual(bounded_tail(values,True)+1e-14,exact)
                self.assertAlmostEqual(bounded_tail(values,True),
                                       bounded_tail([1-v for v in values],False))
        self.assertEqual(bounded_tail([],True),1)
        self.assertEqual(bounded_tail([.5,.5],True),1)
        self.assertAlmostEqual(bounded_tail([0]*8,True),1/256)
        with self.assertRaises(ValueError): bounded_tail([1.5],True)

    def test_nested_windows_retain_local_evidence(self):
        # The entire right-side mean is .6 and would not reject a required
        # C-majority, but the first eight cells strongly contradict it.
        scores=[dict(s=x,observed=float(x>=8)) for x in range(20)]
        self.assertEqual(bounded_tail([r['observed'] for r in scores],True),1)
        self.assertFalse(accepts_candidate(scores,'s',-1,True,'observed',.01))

    def test_theory_ties_and_dominance_are_not_sampled_uncertainty(self):
        tie=dict(s=0,theory_lower=0,theory_upper=1,certain_C=False,certain_D=False)
        for theta in (-1,0,1):
            self.assertTrue(accepts_candidate([tie],'s',theta,True,'theory',.01))
        dominant={**tie,'theory_upper':0,'certain_D':True}
        self.assertFalse(accepts_candidate([dominant],'s',-1,True,'theory',.01))
        self.assertTrue(accepts_candidate([dominant],'s',1,True,'theory',.01))

    def test_confidence_sets_widen_under_multiplicity_and_use_payoff_units(self):
        scores=[dict(s=x,observed=float(x>=5)) for x in range(10) for _ in range(2)]
        individual=threshold_set(scores,'s','observed')
        family=threshold_set(scores,'s','observed',family_size=128)
        self.assertEqual(individual['status'],'finite')
        self.assertLessEqual(individual['low'],4.5)
        self.assertGreaterEqual(individual['high'],4.5)
        self.assertLessEqual(family['low'],individual['low'])
        self.assertGreaterEqual(family['high'],individual['high'])
        shifted=threshold_set([{**r,'s':2*r['s']+3} for r in scores],'s','observed')
        self.assertEqual(shifted['low'],2*individual['low']+3)
        self.assertEqual(shifted['high'],2*individual['high']+3)
        self.assertAlmostEqual(individual['tail_alpha'],.05/(2*10))
        self.assertAlmostEqual(family['tail_alpha'],.05/(2*10*128))

    def test_difference_sets_and_abs_shift_lower_bound(self):
        a=dict(status='finite',low=2,high=3);b=dict(status='finite',low=0,high=1)
        d=difference_set(a,b)
        self.assertEqual((d['low'],d['high'],d['excludes_zero'],d['minimum_abs_shift']),(1,3,True,1))
        self.assertFalse(difference_set(b,b)['excludes_zero'])
        self.assertIsNone(difference_set(dict(status='empty'),b)['excludes_zero'])

    def test_archived_cohort_and_final_comparison_counts(self):
        games=load_games([ROOT/'data/attempts.jsonl.gz',ROOT/'data_pd_refinement/attempts.jsonl.gz'])
        self.assertEqual(len(game_scores(games)),1614)  # not 3228 independent units
        rows=analyze(games);summary=summary_for(rows)
        self.assertEqual(len(rows),128)
        self.assertEqual(summary['individual']['difference_sets'],
                         {'unbounded':113,'one_sided':9,'finite':6})
        self.assertEqual(summary['familywise']['difference_sets'],{'unbounded':128})
        self.assertEqual(summary['individual']['zero_excluded'],0)
        self.assertEqual(summary['familywise']['zero_excluded'],0)
        for r in rows:
            for source in ('observed','theoretical'):
                self.assertLessEqual(r['familywise'][source]['low'],r['individual'][source]['low'])
                self.assertGreaterEqual(r['familywise'][source]['high'],r['individual'][source]['high'])


if __name__=='__main__':unittest.main()
