"""Mathematical checks behind the sweep-design audit; no model calls.

These check equivalences and informative design points, not LLM invariance.
They do not replace or modify any frozen experiment schedule.
"""
from dataclasses import replace
from fractions import Fraction as F
import unittest

from gut.canonical import EXAMPLES
from gut.game import Game
from gut.oversight import ACTIONS, DEFENSES, Oversight


class ParameterizationTests(unittest.TestCase):
    def test_player_specific_affine_changes_preserve_expected_preferences(self):
        # Transform final outcomes, including the intervention. Different scales
        # for each player must not be confused with a shared unchanged cost.
        for name, game in EXAMPLES.items():
            for cost in game.costs:
                original = game.matrix(cost)
                transforms = ((F(10), F(5)), (F(1, 3), F(-7)))
                changed = tuple(tuple(tuple(transforms[r][0]*cell[r]+transforms[r][1]
                                            for r in range(2)) for cell in row)
                                for row in original)
                for role in range(2):
                    for probability in (F(0), F(1, 4), F(1, 2), F(3, 4), F(1)):
                        def margin(table):
                            own = lambda i, j: table[i][j][0] if role == 0 else table[j][i][1]
                            return probability*(own(0, 0)-own(1, 0)) + (1-probability)*(own(0, 1)-own(1, 1))
                        with self.subTest(game=name, cost=cost, role=role, probability=probability):
                            self.assertEqual(margin(changed), transforms[role][0]*margin(original))

    def test_structural_slices_preserve_the_declared_strict_game(self):
        specs = (
            ("pd", F(2), F(-1, 2), (F(3, 2), F(7, 4), F(2)), (F(-3, 4), F(-1, 2), F(-1, 4))),
            ("stag_hunt", F(1, 2), F(-1, 2), (F(1, 4), F(1, 2), F(3, 4)), (F(-3, 4), F(-1, 2), F(-1, 4))),
            ("chicken", F(3, 2), F(1, 2), (F(5, 4), F(3, 2), F(7, 4)), (F(1, 4), F(1, 2), F(3, 4))),
        )
        for name, t0, s0, ts, ss in specs:
            cells = {(t, s0) for t in ts} | {(t0, s) for s in ss}
            self.assertEqual(len(cells), 5)
            for t, s in cells:
                g = Game(t=t, s=s)
                with self.subTest(game=name, t=t, s=s):
                    if name == "pd":
                        self.assertGreater(t, 1)
                        self.assertLess(s, 0)
                        self.assertLess(t+s, 2)  # Extra welfare assumption.
                        self.assertEqual(g.region(), "defection_dominant")
                    elif name == "stag_hunt":
                        self.assertTrue(0 < t < 1 and s < 0)
                        self.assertEqual(g.region(), name)
                    else:
                        self.assertTrue(t > 1 > s > 0)
                        self.assertEqual(g.region(), name)

    def test_resource_quantity_and_value_are_not_independent_payoff_axes(self):
        original, same_product = Oversight(), Oversight(v=2, r=2)
        for d in DEFENSES:
            for action in ACTIONS:
                self.assertEqual(original.payoff(d, action), same_product.payoff(d, action))

    def test_same_oversight_root_does_not_imply_same_payoff_gap(self):
        original = Oversight()
        scaled = replace(original, v=8, a=2, p=6, b=2)
        shifted = replace(original, a=2, b=0)
        self.assertEqual(original.thresholds(0)["d"]["root"], scaled.thresholds(0)["d"]["root"])
        for d in DEFENSES:
            self.assertEqual(scaled.margin(d), 2*original.margin(d))
            self.assertEqual(shifted.margin(d), original.margin(d))
            self.assertEqual(scaled.best_responses(d), original.best_responses(d))
        self.assertNotEqual(scaled.margin(F(3, 10)), original.margin(F(3, 10)))

    def test_attack_cost_slice_brackets_an_exact_tie_on_the_existing_grid(self):
        d = F(3, 10)
        self.assertIn(d, DEFENSES)
        for cost, margin, best in (
            (F(4, 5), F(-1, 10), ("attack",)),
            (F(17, 20), F(-1, 20), ("attack",)),
            (F(9, 10), F(0), ACTIONS),
            (F(19, 20), F(1, 20), ("cooperate",)),
            (F(1), F(1, 10), ("cooperate",)),
        ):
            game = Oversight(a=cost)
            self.assertEqual(game.margin(d), margin)
            self.assertEqual(game.best_responses(d), best)


if __name__ == "__main__":
    unittest.main()
