import itertools
import json
import math
import unittest

from utility_threshold.games.phase_space import PhasePoint, build_phase_grid, normalize_payoffs


class PhaseSpaceTests(unittest.TestCase):
    def test_all_twelve_strict_ordinal_orders_are_distinct(self) -> None:
        orders = set()
        for order in itertools.permutations("RTPS"):
            if order.index("R") > order.index("P"):
                continue
            values = dict(zip(order, (4.0, 3.0, 2.0, 1.0)))
            point = PhasePoint.from_payoffs(
                reward=values["R"], punishment=values["P"],
                sucker=values["S"], temptation=values["T"],
            )
            with self.subTest(order=order):
                self.assertEqual(point.ordinal_order, ">".join(order))
                self.assertEqual(point.to_dict()["ties"], [])
                self.assertEqual(point.degeneracy, "none")
            orders.add(point.ordinal_order)
        self.assertEqual(len(orders), 12)

    def test_canonical_games_and_strict_best_response_quadrants(self) -> None:
        cases = [
            (-0.5, 1.5, "prisoners_dilemma", "competition_dominant", (("D", "D"),), None),
            (0.5, 1.5, "chicken", "anti_coordination", (("C", "D"), ("D", "C")), 0.5),
            (-0.5, 0.5, "stag_hunt", "coordination", (("C", "C"), ("D", "D")), 0.5),
            (0.5, 0.25, "other_strict_ordinal", "cooperation_dominant", (("C", "C"),), None),
        ]
        for s, t, family, quadrant, nash, mixed in cases:
            with self.subTest(s=s, t=t):
                point = PhasePoint(s, t)
                self.assertEqual(point.family, family)
                self.assertEqual(point.quadrant, quadrant)
                self.assertEqual(point.pure_nash, nash)
                self.assertEqual(point.symmetric_mixed_cooperation, mixed)

    def test_prisoners_dilemma_does_not_assume_mutual_cooperation_maximizes_welfare(self) -> None:
        point = PhasePoint(-0.5, 3.0)
        self.assertEqual(point.family, "prisoners_dilemma")
        self.assertEqual(point.pure_nash, (("D", "D"),))
        self.assertEqual(point.welfare_max_profiles, (("C", "D"), ("D", "C")))
        self.assertTrue(point.to_dict()["turn_taking_preferred"])
        # CC is efficient among pure profiles despite being dominated by an
        # equal lottery over the two off-diagonal outcomes.
        self.assertIn(("C", "C"), point.pareto_profiles)
        self.assertEqual(point.to_dict()["pareto_scope"], "pure_profiles_only")

    def test_welfare_bands_and_ties(self) -> None:
        cases = [
            (-3.0, "off_diagonal_below_2P", (("C", "C"),)),
            (-1.0, "off_diagonal_equals_2P", (("C", "C"),)),
            (0.0, "off_diagonal_between_2P_and_2R", (("C", "C"),)),
            (1.0, "off_diagonal_equals_2R", (("C", "C"), ("C", "D"), ("D", "C"))),
            (2.0, "off_diagonal_above_2R", (("C", "D"), ("D", "C"))),
        ]
        for s, band, profiles in cases:
            with self.subTest(s=s):
                point = PhasePoint(s, 1.0)
                self.assertEqual(point.welfare_band, band)
                self.assertEqual(point.welfare_max_profiles, profiles)

    def test_ordinal_tie_need_not_be_a_best_response_boundary(self) -> None:
        point = PhasePoint(0.5, 0.5)
        self.assertEqual(point.ordinal_order, "R>T=S>P")
        self.assertEqual(point.to_dict()["ties"], [["T", "S"]])
        self.assertEqual(point.family, "tie_boundary")
        self.assertEqual(point.quadrant, "cooperation_dominant")
        self.assertEqual(point.degeneracy, "none")

    def test_boundary_equilibrium_continua_are_flagged(self) -> None:
        cases = [
            (0.5, 1.0, "equilibrium_continuum_one_player_C", (("C", "C"), ("C", "D"), ("D", "C"))),
            (0.0, 1.5, "equilibrium_continuum_one_player_D", (("C", "D"), ("D", "C"), ("D", "D"))),
            (0.0, 1.0, "all_strategy_profiles_are_equilibria", (("C", "C"), ("C", "D"), ("D", "C"), ("D", "D"))),
        ]
        for s, t, label, pure in cases:
            with self.subTest(s=s, t=t):
                point = PhasePoint(s, t)
                self.assertEqual(point.quadrant, "boundary")
                self.assertEqual(point.degeneracy, label)
                self.assertTrue(point.equilibrium_continuum)
                self.assertEqual(point.pure_nash, pure)
                self.assertIsNone(point.symmetric_mixed_cooperation)

    def test_boundary_indifference_does_not_always_produce_a_continuum(self) -> None:
        for point in (PhasePoint(-0.5, 1.0), PhasePoint(0.0, 0.5)):
            self.assertEqual(point.pure_nash, (("C", "C"), ("D", "D")))
            self.assertEqual(point.degeneracy, "boundary_indifference_no_continuum")
            self.assertFalse(point.equilibrium_continuum)
            self.assertIsNone(point.symmetric_mixed_cooperation)

    def test_parallel_nonzero_margins_are_not_a_degenerate_equilibrium(self) -> None:
        for point in (PhasePoint(0.5, 0.5), PhasePoint(-0.5, 1.5)):
            self.assertIsNone(point.symmetric_mixed_cooperation)
            self.assertEqual(point.degeneracy, "none")

    def test_mixed_probability_induces_equal_action_utilities(self) -> None:
        for point in (PhasePoint(-2.0, 0.5), PhasePoint(0.2, 3.0)):
            probability = point.symmetric_mixed_cooperation
            assert probability is not None
            self.assertGreater(probability, 0.0)
            self.assertLess(probability, 1.0)
            self.assertAlmostEqual(
                probability * point.R + (1 - probability) * point.S,
                probability * point.T + (1 - probability) * point.P,
            )
            self.assertAlmostEqual(
                probability, (point.P - point.S) / (point.P - point.S + point.R - point.T)
            )

    def test_pure_maximin_can_have_two_actions(self) -> None:
        self.assertEqual(PhasePoint(-0.5, 1.5).pure_maximin_actions, ("D",))
        self.assertEqual(PhasePoint(0.5, 1.5).pure_maximin_actions, ("C",))
        self.assertEqual(PhasePoint(-1.0, -1.0).pure_maximin_actions, ("C", "D"))

    def test_dominance_threshold_uses_both_opponent_actions_and_is_weak(self) -> None:
        point = PhasePoint(-0.5, 1.25, reward=5.0, punishment=1.0)
        self.assertEqual(point.cooperation_margins, {"opponent_C": -1.0, "opponent_D": -2.0})
        self.assertEqual(point.minimum_intervention_for_cooperation_dominance, 2.0)
        threshold = point.minimum_intervention_for_cooperation_dominance
        self.assertTrue(all(margin + threshold >= 0 for margin in point.cooperation_margins.values()))
        self.assertTrue(any(margin + threshold == 0 for margin in point.cooperation_margins.values()))
        self.assertEqual(PhasePoint(0.5, 0.5).minimum_intervention_for_cooperation_dominance, 0.0)

    def test_positive_affine_transform_preserves_strategic_and_welfare_diagnostics(self) -> None:
        base = PhasePoint(-0.5, 1.75)
        scaled = PhasePoint.from_payoffs(reward=-3.0, punishment=-7.0, sucker=-9.0, temptation=0.0)
        self.assertEqual((scaled.s, scaled.t), (base.s, base.t))
        for key in (
            "family", "quadrant", "ordinal_order", "pure_nash", "symmetric_mixed_cooperation",
            "degeneracy", "welfare_max_profiles", "pareto_profiles", "pure_maximin_actions", "welfare_band",
        ):
            self.assertEqual(base.to_dict()[key], scaled.to_dict()[key], key)
        self.assertEqual(scaled.minimum_intervention_for_cooperation_dominance,
                         4.0 * base.minimum_intervention_for_cooperation_dominance)

    def test_matrix_orientation_and_existing_engine_agree(self) -> None:
        point = PhasePoint(-0.5, 1.5, reward=3.0, punishment=1.0)
        game = point.to_game(actions=("PAUSE", "RACE"), game_id="test_phase")
        self.assertEqual(game.game_id, "test_phase")
        self.assertEqual(game.payoff(("PAUSE", "RACE")).row, 0.0)
        self.assertEqual(game.payoff(("PAUSE", "RACE")).column, 4.0)
        self.assertTrue(game.is_symmetric)
        data = point.to_dict()
        self.assertEqual(data["row_payoff_matrix"], [[3.0, 0.0], [4.0, 1.0]])
        self.assertEqual(data["column_payoff_matrix"], [[3.0, 4.0], [0.0, 1.0]])
        self.assertEqual(json.loads(json.dumps(data, allow_nan=False)), data)
        with self.assertRaises(ValueError):
            point.to_game(actions=("C", "C"))

    def test_grid_accepts_generators_and_preserves_order(self) -> None:
        points = build_phase_grid(iter([-1.0, 0.0]), iter([1.5, 0.5]))
        self.assertEqual([(p.s, p.t) for p in points], [(-1.0, 1.5), (0.0, 1.5), (-1.0, 0.5), (0.0, 0.5)])
        self.assertEqual(build_phase_grid([], [1.0]), [])
        with self.assertRaises(ValueError):
            build_phase_grid([], [], reward=0.0, punishment=0.0)

    def test_negative_coordinates_and_negative_utilities_are_valid(self) -> None:
        point = PhasePoint(-3.0, -2.0, reward=-1.0, punishment=-2.0)
        self.assertEqual(point.S, -5.0)
        self.assertEqual(point.T, -4.0)
        self.assertEqual(normalize_payoffs(reward=-1, punishment=-2, sucker=-5, temptation=-4), (-3.0, -2.0))

    def test_nonfinite_values_and_invalid_anchor_order_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            for field in ("s", "t", "reward", "punishment"):
                args = {"s": -0.5, "t": 1.5, field: value}
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    PhasePoint(**args)
            with self.assertRaises(ValueError):
                normalize_payoffs(reward=1, punishment=0, sucker=value, temptation=2)
        for reward, punishment in ((0, 0), (0, 1)):
            with self.assertRaises(ValueError):
                PhasePoint(0, 0, reward=reward, punishment=punishment)
            with self.assertRaises(ValueError):
                normalize_payoffs(reward=reward, punishment=punishment, sucker=0, temptation=2)

    def test_tiny_nonzero_margin_is_not_silently_reclassified_as_tie(self) -> None:
        point = PhasePoint(-1e-12, 1.5)
        self.assertEqual(point.quadrant, "competition_dominant")
        self.assertEqual(point.pure_nash, (("D", "D"),))
        self.assertEqual(point.to_dict()["ties"], [])


if __name__ == "__main__":
    unittest.main()
