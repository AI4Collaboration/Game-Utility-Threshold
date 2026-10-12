import unittest
from utility_threshold.games.phase_space import SymmetricPayoffs, phase_grid, axis_values
from utility_threshold.games.theory_comparison import decision_benchmark, joint_benchmark


class TheoryComparisonTests(unittest.TestCase):
    def test_heatmap_cells_keep_ties_and_exclude_missing_decisions(self):
        from scripts.compare_phase_space_theory import deviation_cells
        p=SymmetricPayoffs(T=.5,R=1,P=0,S=-.5)
        base={'model_key':'glm','stage':'perspective_grid','s':p.s,'t':p.t}
        decisions=[{**base,'job_id':str(i),**decision_benchmark(p,action,q)}
                   for i,(action,q) in enumerate([('C',.5),('D',.8),(None,.5)])]
        games=[{**base,'simulation_id':'game',**joint_benchmark(p,'D','C')}]
        rows=deviation_cells(decisions,games)
        cell=next(r for r in rows if r['model_key']=='glm' and r['s']==-.5 and r['t']==.5)
        self.assertEqual(cell['valid_belief_decisions'],2)
        self.assertEqual(cell['belief_ties'],1)
        self.assertEqual(cell['belief_violation_rate'],.5)
        self.assertAlmostEqual(cell['mean_belief_regret'],.15)
        self.assertEqual(cell['valid_games'],1)
        self.assertAlmostEqual(cell['mean_maximum_realized_regret'],.5)
        missing=next(r for r in rows if r['model_key']=='qwen')
        self.assertIsNone(missing['belief_violation_rate'])
        self.assertEqual(sum(r['valid_belief_decisions'] for r in rows),2)

    def test_baseline_cutoffs_and_regret(self):
        result=decision_benchmark(SymmetricPayoffs(),'C',.5)
        self.assertEqual(result['stated_belief_best_response'],'D')
        self.assertEqual(result['stated_belief_regret_normalized'],.75)
        self.assertFalse(result['dominant_action_chosen'])
        self.assertEqual(result['cost_for_weak_C_at_stated_belief_raw'],1.5)
        self.assertEqual(result['cost_for_weak_C_dominance_raw'],2)
        self.assertEqual([result[f'{x}_threshold_at_stated_belief'] for x in ('T','R','P','S')],[2,6,-2,3])
        self.assertFalse(result['belief_threshold_in_unit_interval'])

    def test_belief_threshold_direction_and_exact_indifference(self):
        coordination=SymmetricPayoffs(T=.5,R=1,P=0,S=-.5)
        anti=SymmetricPayoffs(T=1.5,R=1,P=0,S=.5)
        for p,low,high in [(coordination,'D','C'),(anti,'C','D')]:
            for q,action in [(.4,low),(.6,high)]:
                d=decision_benchmark(p,action,q)
                self.assertEqual(d['belief_threshold_q'],.5)
                self.assertTrue(d['stated_belief_action_consistent'])
            for action in ('C','D'):
                d=decision_benchmark(p,action,.5)
                self.assertTrue(d['stated_belief_tie'])
                self.assertTrue(d['stated_belief_action_consistent'])
                self.assertEqual(d['stated_belief_regret_normalized'],0)

    def test_endpoint_and_parallel_cases_do_not_invent_cutoffs(self):
        p=SymmetricPayoffs(T=1,R=1,P=0,S=0)
        result=decision_benchmark(p,'D',.37)
        self.assertTrue(result['every_belief_indifferent'])
        self.assertIsNone(result['belief_threshold_q'])
        self.assertIsNone(result['strict_dominant_action'])
        zero=decision_benchmark(SymmetricPayoffs(),'D',0)
        one=decision_benchmark(SymmetricPayoffs(),'D',1)
        self.assertIsNone(zero['T_threshold_at_stated_belief'])
        self.assertIsNone(zero['R_threshold_at_stated_belief'])
        self.assertIsNone(one['P_threshold_at_stated_belief'])
        self.assertIsNone(one['S_threshold_at_stated_belief'])

    def test_affine_transforms_preserve_decisions_and_transform_raw_thresholds(self):
        p=SymmetricPayoffs()
        a=decision_benchmark(p,'C',.37)
        b=decision_benchmark(p.affine(7,-5),'C',.37)
        self.assertAlmostEqual(a['stated_belief_regret_normalized'],b['stated_belief_regret_normalized'])
        self.assertEqual(a['stated_belief_best_response'],b['stated_belief_best_response'])
        for x in ('T','R','P','S'):
            self.assertAlmostEqual(b[f'{x}_threshold_at_stated_belief'],7*a[f'{x}_threshold_at_stated_belief']-5)
        self.assertAlmostEqual(b['cost_for_weak_C_at_stated_belief_raw'],7*a['cost_for_weak_C_at_stated_belief_raw'])

    def test_missing_data_remains_missing(self):
        for q in (None,True,float('nan'),1.1):
            r=decision_benchmark(SymmetricPayoffs(),None,q)
            self.assertIsNone(r['stated_belief_action_consistent'])
            self.assertIsNone(r['stated_belief_regret_normalized'])
        r=joint_benchmark(SymmetricPayoffs(),None,'D')
        self.assertFalse(r['valid'])
        self.assertIsNone(r['welfare_gap_normalized'])
        self.assertEqual(r['pure_nash_profiles'],[['D','D']])

    def test_mixed_play_can_generate_non_pure_nash_outcomes(self):
        p=SymmetricPayoffs(T=2,R=1,P=0,S=.5)
        r=joint_benchmark(p,'C','C')
        self.assertAlmostEqual(r['symmetric_interior_mixed_C_probability'],1/3)
        self.assertAlmostEqual(r['pure_nash_outcome_probability_if_independent_mixed_NE'],4/9)
        self.assertFalse(r['nash'])
        self.assertAlmostEqual(r['maximum_unilateral_regret_normalized'],1)
        self.assertAlmostEqual(r['welfare_gap_normalized'],.5)

    def test_full_grid_matches_direct_expected_utilities_and_threshold_roots(self):
        for p in phase_grid(axis_values()):
            for q in (0,.125,.5,.8,1):
                uc=q*p.R+(1-q)*p.S
                ud=q*p.T+(1-q)*p.P
                for action in ('C','D'):
                    r=decision_benchmark(p,action,q)
                    chosen=uc if action=='C' else ud
                    self.assertAlmostEqual(r['stated_belief_regret_normalized'],max(uc,ud)-chosen)
                    self.assertEqual(r['stated_belief_action_consistent'],chosen>=max(uc,ud)-1e-9)
                r=decision_benchmark(p,'C',q)
                for name in ('T','R','P','S'):
                    cut=r[f'{name}_threshold_at_stated_belief']
                    if cut is None: continue
                    vals={key:getattr(p,key) for key in ('T','R','P','S')};vals[name]=cut
                    delta=q*(vals['R']-vals['T'])+(1-q)*(vals['S']-vals['P'])
                    self.assertAlmostEqual(delta,0)


if __name__=='__main__':
    unittest.main()
