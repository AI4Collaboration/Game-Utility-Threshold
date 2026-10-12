import unittest
from run_phase_space import cases,make_jobs,prompt_for,MODELS


class PDRefinementTests(unittest.TestCase):
    def test_new_grid_completes_same_domain_without_repeating_anchors(self):
        old={(c['payoffs']['S'],c['payoffs']['T']) for c in cases('perspective_grid',0) if c['payoffs']['strict_pd']}
        new={(c['payoffs']['S'],c['payoffs']['T']) for c in cases('perspective_pd_refinement',0)}
        self.assertEqual(len(new),33)
        self.assertFalse(old & new)
        self.assertEqual(old | new,{(-1+i/8,1.25+j/8) for i in range(7) for j in range(7)})
        for c in cases('perspective_pd_refinement',0):self.assertTrue(c['payoffs']['strict_pd'])

    def test_balanced_jobs_and_unchanged_own_payoff_prompt(self):
        jobs=[j for b in (0,1) for j in make_jobs('perspective_pd_refinement',b,list(MODELS))]
        self.assertEqual(len(jobs),528)
        self.assertEqual(len({j['job_id'] for j in jobs}),528)
        for c in cases('perspective_pd_refinement',0):
            for role in ('row','column'):
                self.assertEqual(prompt_for(c,role),prompt_for({**c,'stage':'perspective_grid'},role))


if __name__=='__main__':unittest.main()
