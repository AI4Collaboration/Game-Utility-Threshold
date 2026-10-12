import math
import unittest
from pathlib import Path
from scripts.report_threshold_table import (load_games, build_cells, build_rows,
    confidence_band, invert_band, minimum_gap)

ROOT=Path(__file__).resolve().parents[1]


class ThresholdTableTests(unittest.TestCase):
    def test_simultaneous_game_bands_and_monotone_inversion(self):
        for n in (1,2):
            for mean in (0,.25,.5,.75,1):
                self.assertEqual(confidence_band(mean,n,2424),(0,1))
        self.assertEqual(invert_band([(0,0,1),(1,0,1)],True),(-math.inf,math.inf))
        self.assertEqual(invert_band([(0,0,.4),(1,.6,1)],True),(0,1))
        self.assertEqual(invert_band([(0,.6,1),(1,0,.4)],False),(0,1))
        self.assertEqual(invert_band([(0,0,.5),(1,.5,1)],True),(-math.inf,math.inf))
        # For n=1000, a .5 mean has a radius determined by the advertised
        # familywise allocation, not a pointwise 95% critical value.
        lo,hi=confidence_band(.5,1000,2424)
        self.assertAlmostEqual(2*2424*math.exp(-2000*(hi-.5)**2),.05)
        self.assertAlmostEqual(lo,1-hi)

    def test_signed_grid_gap_is_not_midpoint_or_significance(self):
        self.assertEqual(minimum_gap(-.75,-.25),-.25)
        self.assertEqual(minimum_gap(.125,.75),.125)
        self.assertEqual(minimum_gap(-.5,.5),0)
        self.assertEqual(minimum_gap(.125,math.inf),.125)
        self.assertIsNone(minimum_gap(None,None))

    def test_archived_cohort_sparse_slices_and_theory(self):
        games=load_games([ROOT/'data/attempts.jsonl.gz',ROOT/'data_pd_refinement/attempts.jsonl.gz'])
        cells=build_cells(games);rows=build_rows(cells)
        self.assertEqual((len(games),len(cells),len(rows)),(1614,808,128))
        self.assertEqual(sum(c['decisions'] for c in cells),3228)
        self.assertEqual(sum(c['games']==1 for c in cells),2)
        self.assertEqual(len({(c['s'],c['t']) for c in cells}),202)
        # In strict PD D is better for every possible opponent belief.
        pd=[c for c in cells if c['s']<0 and c['t']>1]
        self.assertEqual(len(pd),196)
        self.assertTrue(all(c['theory_min']==c['theory_max']==0 for c in pd))
        self.assertTrue(all(c['theory_min_band']==c['theory_max_band']==(0,0) for c in pd))
        for r in rows:
            self.assertEqual(r['difference_95_set'],(-math.inf,math.inf))
            self.assertIsNone(r['distance_outside_95_set'])
            if r['fixed_value'] in (-.875,-.625,-.375) and r['varied_payoff']=='T':
                self.assertEqual(r['sampled_values'],[1.25,1.375,1.5,1.625,1.75,1.875,2])
            if r['fixed_value'] in (1.375,1.625,1.875) and r['varied_payoff']=='S':
                self.assertEqual(r['sampled_values'],[-1,-.875,-.75,-.625,-.5,-.375,-.25])
        row=next(r for r in rows if r['model_key']=='fable' and r['varied_payoff']=='S' and r['fixed_value']==1.25)
        self.assertEqual((row['difference']['low'],row['difference']['high']),(-.75,-.25))


if __name__=='__main__':unittest.main()
