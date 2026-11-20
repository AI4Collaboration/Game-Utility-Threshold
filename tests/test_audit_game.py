from fractions import Fraction as F
from random import Random
import unittest

from gut.audit_game import ACTIONS, AuditGame, RewardType, demo_game
from gut.commitment import CommitmentGame


class CommitmentTests(unittest.TestCase):
    def test_published_table_1_and_unattained_unfavorable_optimum(self):
        # Paruchuri et al. 2008 Table 1: (leader, follower) pairs.
        game = CommitmentGame([1], [[[1, 0], [0, 2]]], [[[2, 4], [1, 3]]])
        self.assertEqual(game.evaluate(1)["favorable"], 2)
        self.assertEqual(game.evaluate(0)["favorable"], 3)
        self.assertEqual(game.evaluate(F(1, 2))["favorable"], F(7, 2))
        result = game.solve()
        # Analytic optimum derived from that table, not a number reported there.
        self.assertEqual(result["favorable"]["value"], F(11, 3))
        self.assertEqual(result["favorable"]["witnesses"], [F(2, 3)])
        self.assertFalse(result["unfavorable"]["attained"])
        self.assertEqual(result["unfavorable"]["value"], F(11, 3))
        self.assertIn({"q": F(2, 3), "side": "left", "value": F(11, 3)},
                      result["unfavorable"]["limits"])

    def test_persistent_follower_ties_need_leader_intersections(self):
        game = CommitmentGame([1], [[[0, 0], [0, 0]]], [[[1, 0], [0, 1]]])
        result = game.solve()
        self.assertEqual(result["unfavorable"]["value"], F(1, 2))
        self.assertEqual(result["unfavorable"]["witnesses"], [F(1, 2)])
        self.assertEqual(result["favorable"]["value"], 1)

    def test_exact_solver_dominates_independent_grid_and_witnesses_check(self):
        rng = Random(106)
        for _ in range(25):
            follower = [[[rng.randint(-3, 3) for a in range(3)] for row in range(2)] for kind in range(2)]
            leader = [[[rng.randint(-3, 3) for a in range(3)] for row in range(2)] for kind in range(2)]
            game = CommitmentGame([F(1, 3), F(2, 3)], follower, leader)
            solved = game.solve()
            for tie in ("favorable", "unfavorable"):
                for i in range(101):
                    q = F(i, 100)
                    score = F(0)
                    for k, prior in enumerate(game.priors):
                        ai = [q*follower[k][0][a]+(1-q)*follower[k][1][a] for a in range(3)]
                        human = [q*leader[k][0][a]+(1-q)*leader[k][1][a] for a in range(3)]
                        choose = max if tie == "favorable" else min
                        score += prior*choose(human[a] for a in range(3) if ai[a] == max(ai))
                    self.assertLessEqual(score, solved[tie]["value"])
                for q in solved[tie]["witnesses"]:
                    self.assertEqual(game.evaluate(q)[tie], solved[tie]["value"])

    def test_invalid_dimensions_and_priors(self):
        for priors, follower, leader in (([0], [[[0], [1]]], [[[0], [1]]]),
                                         ([1], [[[0]]], [[[0], [1]]]),
                                         ([1], [[[0, 1], [1]]], [[[0], [1]]])):
            with self.assertRaises(ValueError):
                CommitmentGame(priors, follower, leader)


class AuditTests(unittest.TestCase):
    def test_published_payoff_structure_with_hand_calculated_instance(self):
        game = demo_game().mean_game()
        row = game.evaluate(F(1, 2))["types"][0]
        self.assertEqual(row["follower"], (0, F(-1, 4), F(-7, 20)))
        self.assertEqual(row["leader"], (F(-1, 20), F(-3, 5), F(-3, 4)))
        self.assertEqual(row["best_responses"], ("abstain",))
        self.assertEqual(row["margin"], F(1, 4))

    def test_ties_are_ranges_not_guarantees(self):
        game = demo_game(punishment=0).mean_game()
        row = game.evaluate(F(1, 2))
        self.assertEqual(row["types"][0]["best_responses"], ("abstain", "target_a"))
        self.assertEqual(row["attack_probability"], {"lower": 0, "upper": 1})
        self.assertEqual(row["favorable"], 0)
        self.assertEqual(row["unfavorable"], F(-11, 20))

    def test_hidden_type_mean_preservation_and_robust_infeasibility(self):
        known, hidden = demo_game(punishment=0).mean_game(), demo_game("hidden", 0)
        self.assertEqual(hidden.mean_game().types[0].unchecked, known.types[0].unchecked)
        self.assertTrue(known.safe_region()["feasible"])
        self.assertFalse(hidden.safe_region()["feasible"])
        self.assertLess(hidden.safety_optimum()["margin"], 0)
        self.assertEqual(hidden.evaluate(F(1, 2))["attack_probability"],
                         {"lower": F(1, 2), "upper": F(1, 2)})
        zero = demo_game("hidden", spread=0)
        for q in (0, F(2, 7), 1):
            self.assertEqual(zero.evaluate(q)["favorable"], demo_game().mean_game().evaluate(q)["favorable"])

    def test_thresholds_safe_interval_and_strict_slack(self):
        game = demo_game().mean_game()
        self.assertEqual(game.safe_region()["interval"], (F(1, 3), F(11, 15)))
        self.assertEqual(game.safe_region(F(1, 10))["interval"], (F(2, 5), F(2, 3)))
        for row in game.thresholds():
            q = row["checking_probability"]
            if row["target"] == "target_b":
                q = 1-q
            evaluated = game.evaluate(q)["types"][0]
            self.assertEqual(evaluated["follower"][ACTIONS.index(row["target"])], 0)
        optimum = game.safety_optimum()
        self.assertEqual(optimum["margin"], F(3, 10))
        self.assertEqual(optimum["witnesses"], [F(8, 15)])
        self.assertFalse(game.safe_region(F(31, 100))["feasible"])

    def test_no_clipping_unreachable_threshold(self):
        game = AuditGame((RewardType("positive_even_caught", 1, (2, 2), (1, 1)),), punishment=0)
        self.assertEqual(game.thresholds()[0]["checking_probability"], 2)
        self.assertFalse(game.thresholds()[0]["in_domain"])
        self.assertFalse(game.safe_region()["feasible"])

    def test_private_views_and_seeded_sampling(self):
        game = demo_game()
        public = game.defender_view()
        for kind in game.types:
            view = game.attacker_view(F(2, 3), kind.name)
            self.assertEqual(view["public_rules"], public)
            self.assertEqual(view["private_type"], kind.name)
            self.assertNotIn("private_type", public)
            self.assertNotIn("inspected_target", view)
        self.assertEqual(game.sample(F(2, 3), "high", "target_a", Random(15)),
                         game.sample(F(2, 3), "high", "target_a", Random(15)))
        self.assertTrue(game.sample(1, "high", "target_a", Random(0))["caught"])
        self.assertTrue(game.sample(0, "high", "target_b", Random(0))["caught"])
        row = game.sample(1, "high", "abstain", Random(0))
        self.assertFalse(row["violation"])
        self.assertEqual(row["attacker_payoff"], 0)
        self.assertEqual(row["defender_payoff"], F(-1, 20))

    def test_invalid_inputs(self):
        for x in (-1, 2, "nan", True):
            with self.assertRaises(ValueError):
                demo_game(punishment=x)
        for q in (-1, 2, "inf"):
            with self.assertRaises(ValueError):
                demo_game().evaluate(q)
        with self.assertRaises(ValueError):
            demo_game().sample(0, "high", "garbage", Random(0))
        with self.assertRaises(ValueError):
            demo_game().attacker_view(0, "unknown")
        with self.assertRaises(ValueError):
            demo_game().safe_region(-1)


if __name__ == "__main__":
    unittest.main()
