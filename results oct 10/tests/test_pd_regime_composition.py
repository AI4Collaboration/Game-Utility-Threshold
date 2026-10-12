import unittest
from fractions import Fraction as F
from pathlib import Path
from scripts.render_pd_regime_composition import load_baselines,composition,regime,REGIMES


class PDRegimeCompositionTests(unittest.TestCase):
    def test_grid_matches_tested_pd_cohort(self):
        grid,meta=load_baselines(Path(__file__).resolve().parents[1]/'data/summary.json.gz')
        self.assertEqual(len(grid),16)
        self.assertEqual(meta['source_valid_paired_games'],128)
        self.assertEqual(set(meta['source_games_by_model'].values()),{32})
        self.assertTrue(all(T>R>P>S for T,R,P,S in grid))
        self.assertEqual(sum(T-R==P-S for T,R,P,S in grid),4)

    def test_two_routes_and_exact_ties(self):
        payoffs=(F(7,4),F(1),F(0),F(-1,4))
        self.assertEqual(regime(payoffs,0),'D_dominant')
        self.assertEqual(regime(payoffs,F(1,4)),'weak_dominance')
        self.assertEqual(regime(payoffs,F(1,2)),'anti_coordination')
        self.assertEqual(regime(payoffs,1),'C_dominant')
        self.assertEqual(regime((F(5,4),F(1),F(0),F(-3,4)),F(1,2)),'coordination')
        self.assertEqual(regime((F(3,2),F(1),F(0),F(-1,2)),F(1,2)),'fully_indifferent')

    def test_interval_counts_and_exact_events_partition_baselines(self):
        grid=[(F(t,4),F(1),F(0),F(-s,4)) for t in range(5,9) for s in range(1,5)]
        _,intervals,events=composition(grid)
        for row in intervals:
            self.assertEqual(sum(row[k+'_count'] for k in REGIMES),16)
            lo,hi=F(row['left_exact']),F(row['right_exact'])
            self.assertEqual([regime(p,(2*lo+hi)/3) for p in grid],
                             [regime(p,(lo+2*hi)/3) for p in grid])
        for row in events:
            self.assertEqual(sum(row[k+'_count'] for k in (*REGIMES,'weak_dominance','fully_indifferent')),16)
        self.assertEqual(intervals[0]['D_dominant_count'],16)
        self.assertEqual(intervals[-1]['C_dominant_count'],16)
        self.assertEqual([intervals[2][k+'_count'] for k in REGIMES],[4,4,4,4])
        self.assertEqual((events[0]['z_exact'],events[0]['weak_dominance_count'],events[0]['fully_indifferent_count']),('1/4',6,1))


if __name__=='__main__':unittest.main()
