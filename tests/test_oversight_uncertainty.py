"""Independent numerical checks of private-type and bounded-error results."""

import itertools
import json
import math
import unittest
from decimal import Decimal
from fractions import Fraction as F

from utility_threshold.core import GameParams, GameState, human_utility, threshold_action
from utility_threshold.oversight_uncertainty import (
    ClosedInterval,
    MarginUncertainty,
    PrivateValue,
    TypeDistribution,
    evaluate_private_values,
    minimum_defense_for_attack_probability,
    one_parameter_distances,
    solve_private_value_defense,
    worst_case_margin,
    worst_case_margin_at_defense,
)


def manual_evaluation(types, defense, prm):
    """Direct payoff table sum; does not invoke new evaluation/threshold helpers."""
    q = min(F(1), F(3, 20) * defense)
    attack_mass = F(0)
    welfare = F(0)
    for v, probability in types:
        attack = v * F(str(prm.R)) - defense / 2 - q * F(str(prm.p)) > F(str(prm.g))
        attack_mass += probability if attack else 0
        value = -F(str(prm.defense_cost_scale)) * defense**2
        if attack:
            value -= (1 - q) * F(str(prm.L))
        welfare += probability * value
    return attack_mass, welfare


class PrivatePriorityTests(unittest.TestCase):
    def test_distribution_requires_explicit_normalization(self):
        with self.assertRaisesRegex(ValueError, "sum exactly"):
            TypeDistribution(tuple(PrivateValue(v, 0.333333) for v in (1, 2, 3)))
        prior = TypeDistribution.from_weights(((1, 1), (2, 1), (3, 1)))
        self.assertEqual(tuple(item.probability for item in prior.types), (F(1, 3),) * 3)
        decimal_prior = TypeDistribution((PrivateValue(1, Decimal("0.1")), PrivateValue(2, 0.9)))
        self.assertEqual(decimal_prior.types[0].probability, F(1, 10))

    def test_invalid_inputs_fail_before_computation(self):
        for value in (math.nan, math.inf, -math.inf, -1, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PrivateValue(value, 1)
        for probability in (math.nan, math.inf, -0.01, 1.01, False):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                PrivateValue(1, probability)
        for values in ((), ((1, 0),), ((1, -1),), ((1, math.inf),)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                TypeDistribution.from_weights(values)
        with self.assertRaises(ValueError):
            TypeDistribution(())
        prior = TypeDistribution((PrivateValue(1, 1),))
        for maximum in (math.nan, math.inf, -1, True):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                solve_private_value_defense(prior, GameParams(), maximum)
        for target in (math.nan, math.inf, -0.1, 1.1):
            with self.subTest(target=target), self.assertRaises(ValueError):
                minimum_defense_for_attack_probability(prior, GameParams(), target)

    def test_private_information_cannot_be_replaced_by_mean_type(self):
        prior = TypeDistribution((PrivateValue(0, 0.5), PrivateValue(10, 0.5)))
        mean_type = TypeDistribution((PrivateValue(5, 1),))
        actual = evaluate_private_values(prior, 4, GameParams())
        naive = evaluate_private_values(mean_type, 4, GameParams())
        self.assertEqual(actual.attack_probability, F(1, 2))
        self.assertEqual(naive.attack_probability, 0)
        self.assertNotEqual(actual.expected_human_utility, naive.expected_human_utility)

    def test_risk_and_damage_have_different_meanings(self):
        prior = TypeDistribution((PrivateValue(100, 1),))
        evaluated = evaluate_private_values(prior, F(20, 3), GameParams())
        self.assertEqual(evaluated.attack_probability, 1)
        self.assertEqual(evaluated.unblocked_attack_probability, 0)
        self.assertEqual(evaluated.expected_human_utility, -F(40, 3))

    def test_stationary_point_uses_current_attacking_mass(self):
        prior = TypeDistribution((PrivateValue(1, 0.5), PrivateValue(100, 0.5)))
        solution = solve_private_value_defense(prior, GameParams())
        self.assertEqual(solution.defense, F(5, 2))
        self.assertEqual(solution.attack_probability, F(1, 2))
        self.assertEqual(solution.expected_human_utility, -F(65, 8))
        selected = next(c for c in solution.candidates if c.evaluation == solution.best)
        self.assertIn("active_type_mass_stationary_point", selected.reasons)
        wrong_stationary = evaluate_private_values(prior, 5, GameParams())
        self.assertGreater(solution.expected_human_utility, wrong_stationary.expected_human_utility)

    def test_exact_threshold_prevents_false_attack_due_to_rounding(self):
        prior = TypeDistribution((PrivateValue(1, 1),))
        prm = GameParams(p=3)
        solution = solve_private_value_defense(prior, prm)
        self.assertEqual(solution.defense, F(20, 19))
        self.assertEqual(solution.best.responses[0].safety_margin, 0)
        self.assertEqual(solution.best.responses[0].action, "COOPERATE")
        # The display float is slightly below the true threshold in the declared
        # decimal model. Feeding it back is a different experimental condition.
        rounded = evaluate_private_values(prior, float(solution.defense), prm)
        self.assertEqual(rounded.responses[0].action, "ATTACK")
        serialized = json.loads(json.dumps(solution.to_dict(), allow_nan=False))
        self.assertEqual(serialized["best"]["defense"], {"numerator": 20, "denominator": 19})

    def test_thresholds_cover_before_at_and_after_saturation(self):
        prior = TypeDistribution.from_weights(((1, 1), (F(25, 3), 1), (10, 1)))
        solution = solve_private_value_defense(prior, GameParams(), 10)
        self.assertEqual(tuple(t.defense for t in solution.type_thresholds), (F(4, 5), F(20, 3), F(10)))
        for threshold in solution.type_thresholds:
            single = TypeDistribution((PrivateValue(threshold.v, 1),))
            at = evaluate_private_values(single, threshold.defense, GameParams())
            below = evaluate_private_values(single, threshold.defense - F(1, 10**8), GameParams())
            self.assertEqual(at.attack_probability, 0)
            self.assertEqual(at.responses[0].safety_margin, 0)
            self.assertEqual(below.attack_probability, 1)

    def test_zero_cost_zero_loss_zero_budget_and_negative_cooperation_reward(self):
        prior = TypeDistribution((PrivateValue(1, 0.5), PrivateValue(5, 0.5)))
        flat = solve_private_value_defense(prior, GameParams(L=0, defense_cost_scale=0))
        self.assertEqual(flat.defense, 4)  # welfare ties: lower risk, then less defense
        no_budget = solve_private_value_defense(prior, GameParams(), 0)
        self.assertEqual(len(no_budget.candidates), 1)
        self.assertEqual(no_budget.attack_probability, 1)
        negative_g = solve_private_value_defense(
            TypeDistribution((PrivateValue(0, 1),)), GameParams(g=-1),
        )
        self.assertEqual(negative_g.type_thresholds[0].defense, F(4, 5))
        no_loss = solve_private_value_defense(prior, GameParams(L=0))
        self.assertEqual(no_loss.defense, 0)

    def test_full_candidate_certificate_dominates_independent_dense_grid(self):
        types = ((F(1), F(1, 4)), (F(4), F(1, 2)), (F(20), F(1, 4)))
        prior = TypeDistribution(tuple(PrivateValue(v, probability) for v, probability in types))
        for loss, cost, maximum, g in itertools.product((0, 3, 30), (0, 0.3, 2), (2, 10), (-1, 1)):
            prm = GameParams(L=loss, defense_cost_scale=cost, g=g)
            solution = solve_private_value_defense(prior, prm, maximum)
            with self.subTest(loss=loss, cost=cost, maximum=maximum, g=g):
                for index in range(401):
                    defense = F(maximum * index, 400)
                    risk, welfare = manual_evaluation(types, defense, prm)
                    self.assertGreaterEqual(solution.expected_human_utility, welfare)
                for candidate in solution.candidates:
                    risk, welfare = manual_evaluation(types, candidate.evaluation.defense, prm)
                    self.assertEqual(candidate.evaluation.attack_probability, risk)
                    self.assertEqual(candidate.evaluation.expected_human_utility, welfare)

    def test_evaluation_agrees_with_legacy_core_away_from_ties(self):
        prior = TypeDistribution((PrivateValue(1, 0.2), PrivateValue(9, 0.8)))
        prm = GameParams()
        for defense in (0, 0.2, 1.3, 5.5, 9):
            result = evaluate_private_values(prior, defense, prm)
            expected = 0.0
            for item, response in zip(prior.types, result.responses):
                state = GameState(v=float(item.v), d=defense)
                action = threshold_action(state, prm)
                self.assertEqual(response.action, action)
                expected += float(item.probability) * human_utility(action, state, prm)
            self.assertAlmostEqual(float(result.expected_human_utility), expected)

    def test_minimum_risk_defense_and_infeasibility_are_explicit(self):
        prior = TypeDistribution((PrivateValue(0, 0.25), PrivateValue(2, 0.5), PrivateValue(10, 0.25)))
        feasible = minimum_defense_for_attack_probability(prior, GameParams(), F(1, 4), 2)
        self.assertTrue(feasible.feasible)
        self.assertEqual(feasible.minimum_defense, F(8, 5))
        self.assertEqual(feasible.evaluation.attack_probability, F(1, 4))
        for i in range(160):
            before = evaluate_private_values(prior, F(i, 100), GameParams())
            self.assertGreater(before.attack_probability, F(1, 4))
        infeasible = minimum_defense_for_attack_probability(prior, GameParams(), 0, 2)
        self.assertFalse(infeasible.feasible)
        self.assertIsNone(infeasible.minimum_defense)
        self.assertIsNone(infeasible.evaluation)
        self.assertEqual(infeasible.best_achievable_attack_probability, F(1, 4))
        unconstrained = minimum_defense_for_attack_probability(prior, GameParams(), 1, 2)
        self.assertEqual(unconstrained.minimum_defense, 0)

    def test_zero_mass_high_type_does_not_prevent_risk_zero(self):
        prior = TypeDistribution((PrivateValue(0, 1), PrivateValue(10**10, 0)))
        solution = minimum_defense_for_attack_probability(prior, GameParams(), 0, 0)
        self.assertTrue(solution.feasible)
        self.assertEqual(solution.minimum_defense, 0)


class BoundedErrorTests(unittest.TestCase):
    def setUp(self):
        self.uncertainty = MarginUncertainty(
            v=ClosedInterval(3, 4), R=ClosedInterval(1, 1.2), g=ClosedInterval(0, 0.2),
            penalty=ClosedInterval(4, 5), detection=ClosedInterval(0.5, 0.6),
            attack_cost=ClosedInterval(2, 2.1),
        )

    def test_box_extrema_equal_all_corner_enumeration(self):
        u = self.uncertainty
        margins = []
        for v, R, g, p, q, c in itertools.product(
            *[(interval.lower, interval.upper) for interval in
              (u.v, u.R, u.g, u.penalty, u.detection, u.attack_cost)]
        ):
            margins.append(g + c + q * p - v * R)
        certificate = worst_case_margin(u)
        self.assertEqual(certificate.minimum_margin, min(margins))
        self.assertEqual(certificate.maximum_margin, max(margins))
        self.assertEqual(certificate.minimum_margin, -F(4, 5))
        self.assertEqual(certificate.maximum_margin, F(23, 10))
        for witness, expected in ((certificate.minimum_witness, min(margins)),
                                  (certificate.maximum_witness, max(margins))):
            value = witness["g"] + witness["attack_cost"] + witness["detection"] * witness["penalty"] - witness["v"] * witness["R"]
            self.assertEqual(value, expected)

    def test_maximin_cooperation_does_not_imply_uniform_cooperation(self):
        certificate = worst_case_margin(self.uncertainty)
        self.assertEqual(certificate.maximin_action, "COOPERATE")
        self.assertGreater(certificate.worst_case_cooperate_utility, certificate.worst_case_attack_utility)
        self.assertFalse(certificate.uniformly_cooperative)
        self.assertFalse(certificate.uniformly_attacking)
        self.assertLess(certificate.minimum_margin, 0)  # an admitted point prefers attack

    def test_shared_defense_bounds_preserve_dependence_and_saturation(self):
        intervals = {
            "v": ClosedInterval(0, 4), "R": ClosedInterval(1, 2), "g": ClosedInterval(-0.1, 1),
            "penalty": ClosedInterval(0, 5), "defense": ClosedInterval(5, 8),
            "detection_slope": ClosedInterval(0.1, 0.2), "attack_cost_slope": ClosedInterval(0.4, 0.6),
        }
        certificate = worst_case_margin_at_defense(**intervals)
        margins = []
        for v, R, g, p, d, b, a in itertools.product(
            *[(interval.lower, interval.upper) for interval in intervals.values()]
        ):
            margins.append(g + a * d + min(1, b * d) * p - v * R)
        self.assertEqual(certificate.minimum_margin, min(margins))
        self.assertEqual(certificate.maximum_margin, max(margins))
        for witness in (certificate.minimum_witness, certificate.maximum_witness):
            self.assertEqual(witness["detection"], min(1, witness["defense"] * witness["detection_slope"]))
            self.assertEqual(witness["attack_cost"], witness["defense"] * witness["attack_cost_slope"])

    def test_exact_tie_is_cooperative_but_has_no_positive_buffer(self):
        point = lambda value: ClosedInterval(value, value)
        u = MarginUncertainty(point(4), point(1), point(0), point(5), point(F(12, 25)), point(F(8, 5)))
        certificate = worst_case_margin(u, F(1, 10**15))
        self.assertEqual(certificate.minimum_margin, 0)
        self.assertTrue(certificate.uniformly_cooperative)
        self.assertFalse(certificate.required_margin_certified)
        self.assertFalse(certificate.uniformly_attacking)

    def test_interval_domains_and_nonfinite_values_are_rejected(self):
        for args in ((2, 1), (0, math.inf), (math.nan, 0), (Decimal("NaN"), 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                ClosedInterval(*args)
        base = dict(vars(self.uncertainty))
        for name, interval in (
            ("v", ClosedInterval(-1, 4)), ("R", ClosedInterval(0, 1)),
            ("penalty", ClosedInterval(-1, 5)), ("detection", ClosedInterval(0, 1.1)),
            ("attack_cost", ClosedInterval(-1, 2)),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                MarginUncertainty(**{**base, name: interval})
        for required in (-1, math.inf, math.nan):
            with self.subTest(required=required), self.assertRaises(ValueError):
                worst_case_margin(self.uncertainty, required)

    def test_one_at_a_time_distances_land_on_ties_and_strict_crossings(self):
        report = one_parameter_distances(GameState(v=4, d=4), GameParams())
        self.assertEqual(report.nominal_margin, 1)
        distances = {item.parameter: item for item in report.distances}
        self.assertEqual(distances["v"].distance_to_tie, 1)
        self.assertEqual(distances["R"].distance_to_tie, F(1, 4))
        self.assertEqual(distances["g"].distance_to_tie, 1)
        self.assertEqual(distances["penalty"].distance_to_tie, F(5, 3))
        self.assertEqual(distances["detection"].distance_to_tie, F(1, 5))
        self.assertEqual(distances["attack_cost"].distance_to_tie, 1)
        self.assertEqual(distances["defense"].distance_to_tie, F(4, 5))
        base = {"v": F(4), "R": F(1), "g": F(0), "penalty": F(5), "detection": F(3, 5), "attack_cost": F(2)}
        for parameter, record in distances.items():
            self.assertTrue(record.attack_possible_beyond_boundary)
            for displacement, expected in ((F(0), 0), (F(1, 10**8), -1)):
                values = base.copy()
                change = displacement if record.adverse_direction == "increase" else -displacement
                boundary = record.boundary_value + change
                if parameter == "defense":
                    values["detection"] = min(1, F(3, 20) * boundary)
                    values["attack_cost"] = boundary / 2
                else:
                    values[parameter] = boundary
                margin = values["g"] + values["attack_cost"] + values["detection"] * values["penalty"] - values["v"] * values["R"]
                self.assertEqual((margin > 0) - (margin < 0), expected)

    def test_unreachable_and_domain_boundary_distances_are_distinguished(self):
        report = one_parameter_distances(GameState(v=0, d=4), GameParams(g=1, p=0))
        distances = {item.parameter: item for item in report.distances}
        for parameter in ("R", "detection", "defense"):
            self.assertIsNone(distances[parameter].distance_to_tie)
            self.assertFalse(distances[parameter].attack_possible_beyond_boundary)
        at_domain_edge = one_parameter_distances(GameState(v=2, d=4), GameParams())
        penalty = next(item for item in at_domain_edge.distances if item.parameter == "penalty")
        self.assertEqual(penalty.boundary_value, 0)
        self.assertFalse(penalty.attack_possible_beyond_boundary)
        with self.assertRaisesRegex(ValueError, "nominally cooperative"):
            one_parameter_distances(GameState(v=100, d=0), GameParams())

    def test_already_tied_zero_effect_parameter_has_zero_distance_but_no_crossing(self):
        report = one_parameter_distances(GameState(v=0, d=0), GameParams(p=0))
        distances = {item.parameter: item for item in report.distances}
        for parameter in ("R", "detection", "penalty"):
            self.assertEqual(distances[parameter].distance_to_tie, 0)
            self.assertFalse(distances[parameter].attack_possible_beyond_boundary)


if __name__ == "__main__":
    unittest.main()
