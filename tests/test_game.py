"""Exact examples, boundary checks, and normalization invariants."""

from decimal import Decimal
from fractions import Fraction as F
import unittest

from gut import BASELINE_PD, Game, grid_counts, pd_grid


class GameTests(unittest.TestCase):
    def test_baseline_and_cost_charge_only_the_player_choosing_d(self):
        self.assertEqual(BASELINE_PD.matrix(), (((3, 3), (0, 5)), ((5, 0), (1, 1))))
        self.assertEqual(BASELINE_PD.matrix(F(3, 2)),
                         (((3, 3), (0, F(7, 2))), ((F(7, 2), 0), (F(-1, 2), F(-1, 2)))))
        self.assertEqual(BASELINE_PD.thresholds(), (2, 1))

    def test_baseline_passes_through_chicken_and_preserves_both_ties(self):
        expected = [(0, "defection_dominant"), (1, "boundary"),
                    (F(3, 2), "chicken"), (2, "boundary"), (3, "cooperation_dominant")]
        for k, region in expected:
            with self.subTest(k=k):
                self.assertEqual(BASELINE_PD.region(k), region)
        self.assertEqual(BASELINE_PD.margins(1), (-1, 0))
        self.assertEqual(BASELINE_PD.margins(2), (0, 1))

    def test_threshold_sides_and_exact_ties(self):
        epsilon = F(1, 10**30)
        for index, threshold in enumerate(BASELINE_PD.thresholds()):
            self.assertLess(BASELINE_PD.margins(threshold-epsilon)[index], 0)
            self.assertEqual(BASELINE_PD.margins(threshold)[index], 0)
            self.assertGreater(BASELINE_PD.margins(threshold+epsilon)[index], 0)

    def test_post_chicken_path(self):
        game = Game(t=2, s="-1/2")
        self.assertEqual(game.thresholds(), (1, F(1, 2)))
        self.assertEqual(game.region(F(3, 4)), "chicken")
        self.assertEqual(game.response_to_defection(F(1, 2)), "tie")

    def test_post_stag_hunt_path(self):
        game = Game(t="3/2", s=-1)
        self.assertEqual(game.thresholds(), (F(1, 2), 1))
        self.assertEqual(game.region(F(3, 4)), "stag_hunt")
        self.assertEqual(game.response_to_defection(F(3, 4)), "defect")
        self.assertEqual(game.region(F(1, 2)), "boundary")
        self.assertEqual(game.region(1), "boundary")
        self.assertEqual(game.region(F(5, 4)), "cooperation_dominant")

    def test_simultaneous_threshold_has_no_artificial_intermediate_region(self):
        game = Game(t=2, s=-1)
        self.assertEqual(game.region(F(999, 1000)), "defection_dominant")
        self.assertEqual(game.margins(1), (0, 0))
        self.assertEqual(game.region(1), "boundary")
        self.assertEqual(game.region(F(1001, 1000)), "cooperation_dominant")

    def test_other_regions_and_zero_payoff_margins_are_supported(self):
        cases = [(F(3, 2), F(-1, 2), "defection_dominant"),
                 (F(1, 2), F(1, 2), "cooperation_dominant"),
                 (F(1, 2), F(-1, 2), "stag_hunt"),
                 (F(3, 2), F(1, 2), "chicken"),
                 (1, -1, "boundary"), (2, 0, "boundary"), (1, 0, "boundary")]
        for t, s, expected in cases:
            with self.subTest(t=t, s=s):
                self.assertEqual(Game(t=t, s=s).region(), expected)

    def test_conditional_response_does_not_require_a_dominant_action(self):
        game = Game(t=2, s="-1/2")
        self.assertEqual(game.response_to_defection(F(1, 4)), "defect")
        self.assertEqual(game.response_to_defection(F(1, 2)), "tie")
        self.assertEqual(game.response_to_defection(F(3, 4)), "cooperate")
        self.assertEqual(game.region(F(3, 4)), "chicken")

    def test_decimal_inputs_are_exact(self):
        game = Game(t=1.1, s=Decimal("-0.1"))
        self.assertEqual(game.t, F(11, 10))
        self.assertEqual(game.s, F(-1, 10))
        self.assertEqual(game.thresholds(), (F(1, 10), F(1, 10)))
        self.assertEqual(game.region(0.1), "boundary")

    def test_baseline_normalization_scales_both_thresholds_and_cost(self):
        normalized = BASELINE_PD.normalized()
        self.assertEqual(normalized, Game(t=2, s=F(-1, 2)))
        self.assertEqual(normalized.thresholds(), (1, F(1, 2)))
        self.assertEqual(BASELINE_PD.normalize_cost(F(3, 2)), F(3, 4))

    def test_normalization_preserves_adjusted_payoffs_and_decisions(self):
        # Include offsets, fractional scales, both paths, and boundary costs.
        for original in (BASELINE_PD, Game(t=7, r=5, p=1, s=-7),
                         Game(t=F(7, 3), r=F(4, 3), p=F(-2, 3), s=-2)):
            normalized = original.normalized()
            gap = original.r-original.p
            for k in (0, *original.thresholds(), F(3, 2), 10):
                with self.subTest(game=original, k=k):
                    z = original.normalize_cost(k)
                    transformed = tuple(tuple(tuple((v-original.p)/gap for v in pair)
                                              for pair in row) for row in original.matrix(k))
                    self.assertEqual(normalized.matrix(z), transformed)
                    self.assertEqual(normalized.margins(z), tuple(v/gap for v in original.margins(k)))
                    self.assertEqual(normalized.region(z), original.region(k))
                    self.assertEqual(normalized.response_to_defection(z), original.response_to_defection(k))

    def test_positive_affine_changes_require_scaling_penalty(self):
        original = Game(t=2, s=F(-1, 2))
        scale, offset = F(7, 3), F(-9, 2)
        changed = Game(t=scale*original.t+offset, s=scale*original.s+offset,
                       r=scale*original.r+offset, p=scale*original.p+offset)
        self.assertEqual(changed.normalized(), original)
        for k in (0, F(1, 2), F(3, 4), 1, 2):
            self.assertEqual(changed.region(scale*k), original.region(k))
            self.assertEqual(changed.normalize_cost(scale*k), k)

    def test_grid_is_exactly_the_declared_625_strict_pd_tables(self):
        games = pd_grid()
        self.assertEqual(len(games), 625)
        self.assertEqual(len(set(games)), 625)
        s_values = sorted({g.s for g in games})
        t_values = sorted({g.t for g in games})
        self.assertEqual((len(s_values), len(t_values)), (25, 25))
        self.assertEqual((s_values[0], s_values[-1]), (-1, F(-1, 20)))
        self.assertEqual((t_values[0], t_values[-1]), (F(21, 20), 2))
        for values in (s_values, t_values):
            self.assertEqual({b-a for a, b in zip(values, values[1:])}, {F(19, 480)})
        self.assertTrue(all(g.t > g.r > g.p > g.s for g in games))

    def test_grid_conditional_counts_keep_ties_separate(self):
        expected = [(0, (0, 625, 0)), (F(1, 20), (0, 600, 25)),
                    (F(1, 2), (300, 325, 0)), (1, (600, 0, 25)), (2, (625, 0, 0))]
        for k, counts in expected:
            with self.subTest(k=k):
                result = grid_counts(k)
                self.assertEqual(result, dict(zip(("cooperate", "defect", "tie"), counts)))
                self.assertEqual(sum(result.values()), 625)

    def test_invalid_numbers_are_rejected_in_every_payoff_field(self):
        for value in (True, None, complex(1), "", "1/0", "NaN", "Infinity",
                      float("nan"), float("inf"), float("-inf"), Decimal("NaN")):
            for name in ("t", "r", "p", "s"):
                with self.subTest(value=value, name=name), self.assertRaises(ValueError):
                    Game(**{**dict(t=2, s=-1, r=1, p=0), name: value})

    def test_equal_or_reversed_baseline_diagonals_are_rejected(self):
        for r, p in ((0, 0), (0, 1), (-2, -1)):
            with self.assertRaises(ValueError):
                Game(t=2, s=-1, r=r, p=p)

    def test_invalid_costs_are_rejected_by_every_cost_operation(self):
        for value in (-1, True, float("nan"), float("inf"), "-1/3", "1/0"):
            for operation in (BASELINE_PD.matrix, BASELINE_PD.margins, BASELINE_PD.region,
                              BASELINE_PD.response_to_defection, BASELINE_PD.normalize_cost,
                              grid_counts):
                with self.subTest(value=value, operation=operation), self.assertRaises(ValueError):
                    operation(value)


if __name__ == "__main__":
    unittest.main()
