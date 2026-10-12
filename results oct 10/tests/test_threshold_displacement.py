import unittest
from scripts.render_threshold_displacement import cell_values, crossing_bracket, displacement, complete_game_records, cooperation_deviation

class ThresholdDisplacementTests(unittest.TestCase):
    def test_signed_cooperation_deviation_respects_indifference_ranges(self):
        self.assertEqual(cooperation_deviation(.75,.25,.25),50)
        self.assertEqual(cooperation_deviation(.25,.75,.75),-50)
        self.assertEqual(cooperation_deviation(.5,.25,.75),0)
        self.assertEqual(cooperation_deviation(1,.25,.75),25)
        self.assertEqual(cooperation_deviation(0,.25,.75),-25)
        self.assertEqual(cooperation_deviation(1,0,1),0)
        self.assertIsNone(cooperation_deviation(None,None,None))

    def test_complete_game_cohort_excludes_valid_partner_of_invalid_decision(self):
        def record(role,valid=True,q=.5):
            return {'job_id':role,'model_key':'glm','role':role,
                    'case':{'stage':'perspective_grid','replicate':0,'case_id':'x'},
                    'decision':{'valid':valid,'action':'C' if valid else None,'belief_opponent_C':q}}
        row=record('row');column=record('column')
        self.assertEqual(len(complete_game_records([row,column])),2)
        self.assertEqual(complete_game_records([row]),[])
        self.assertEqual(complete_game_records([row,record('column',False)]),[])
        self.assertEqual(complete_game_records([row,column,record('column',False)]),[])
        with self.assertRaises(ValueError):complete_game_records([row,record('column',q=None)])

    def test_crossing_brackets_span_tied_samples_without_point_estimates(self):
        b=crossing_bracket([(0,-1),(.25,0),(.5,0),(.75,1)],True)
        self.assertEqual((b['status'],b['low'],b['high']),('bracketed',0,.75))
        b=crossing_bracket([(0,1),(.25,0),(.5,-1)],False)
        self.assertEqual((b['low'],b['high']),(0,.5))

    def test_multiple_or_reversed_crossings_do_not_get_a_unique_threshold(self):
        for points in [[(0,-1),(.25,1),(.5,-1)],[(0,1),(.5,-1)]]:
            self.assertEqual(crossing_bracket(points,True)['status'],'multiple_or_reversed')

    def test_missing_and_indifferent_slices_stay_unresolved(self):
        self.assertEqual(crossing_bracket([(0,None),(.25,1)],True)['status'],'missing')
        b=crossing_bracket([(0,0),(.25,0)],True)
        self.assertEqual(b['status'],'ambiguous')
        self.assertEqual(displacement(b,b)['status'],'unresolved')

    def test_one_sided_bound_uses_last_decisive_point_not_grid_edge(self):
        b=crossing_bracket([(0,-1),(.25,0),(.5,0)],True)
        self.assertEqual((b['status'],b['low'],b['high']),('lower_bound_only',0,float('inf')))
        self.assertEqual(displacement(b,b)['status'],'unresolved')

    def test_displacement_subtracts_intervals_not_midpoints(self):
        a={'status':'bracketed','low':-.25,'high':0}
        b={'status':'bracketed','low':.25,'high':.5}
        self.assertEqual(displacement(a,b),{'status':'bracketed','low':-.75,'high':-.25})
        self.assertEqual(displacement(b,b),{'status':'bracketed','low':-.25,'high':.25})

    def test_reported_beliefs_and_exact_ties_are_used_per_decision(self):
        def record(i,action,q):
            return {'job_id':str(i),'model_key':'glm','case':{'stage':'perspective_grid','payoffs':{'R':1,'P':0,'S':-.5,'T':.5,'s':-.5,'t':.5}},
                    'decision':{'valid':True,'action':action,'belief_opponent_C':q}}
        rows=cell_values([record(0,'C',.9),record(1,'D',.1),record(2,'C',.5),record(3,'D',None)])
        c=next(c for c in rows if c['model_key']=='glm' and c['s']==-.5 and c['t']==.5)
        self.assertEqual(c['n'],3)
        self.assertEqual(c['observed_majority'],1)
        self.assertEqual(c['theory_majority'],0)
        self.assertEqual((c['theory_C_rate_min'],c['theory_C_rate_max']),(1/3,2/3))
        self.assertEqual(c['indifferent'],1)

    def test_overlapping_crossing_brackets_cannot_establish_a_shift(self):
        a=crossing_bracket([(0,1),(.25,-1),(.5,-1)],False)
        b=crossing_bracket([(0,1),(.25,0),(.5,-1)],False)
        delta=displacement(a,b)
        self.assertLessEqual(delta['low'],0)
        self.assertGreaterEqual(delta['high'],0)

if __name__=='__main__':unittest.main()
