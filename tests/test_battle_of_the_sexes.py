import unittest

from utility_threshold.games import (
    BattleOfTheSexesParameters,
    battle_of_the_sexes,
    battle_of_the_sexes_report,
)


class BattleOfTheSexesTests(unittest.TestCase):
    def test_parameter_ordering_is_strict(self) -> None:
        with self.assertRaisesRegex(ValueError, "Battle of the Sexes requires"):
            BattleOfTheSexesParameters(
                preferred_coordination=3,
                concession_coordination=3,
                miscoordination=0,
            )

    def test_two_coordinated_equilibria_encode_opposed_preferences(self) -> None:
        game = battle_of_the_sexes()
        self.assertFalse(game.is_symmetric)
        self.assertEqual(
            game.pure_nash_equilibria(),
            (("OPTION_A", "OPTION_A"), ("OPTION_B", "OPTION_B")),
        )
        self.assertEqual(game.pareto_efficient_profiles(), game.coordination_profiles)
        self.assertEqual(game.welfare_optimal_profiles(), game.coordination_profiles)
        self.assertGreater(game.payoff(("OPTION_A", "OPTION_A")).row, game.payoff(("OPTION_B", "OPTION_B")).row)
        self.assertGreater(game.payoff(("OPTION_B", "OPTION_B")).column, game.payoff(("OPTION_A", "OPTION_A")).column)

    def test_report_exposes_asymmetric_mixing_and_coordination_risk(self) -> None:
        report = battle_of_the_sexes_report()
        self.assertAlmostEqual(report.mixed_equilibrium["row"]["OPTION_A"], 4 / 7)
        self.assertAlmostEqual(report.mixed_equilibrium["column"]["OPTION_A"], 3 / 7)
        self.assertAlmostEqual(report.mixed_coordination_probability, 24 / 49)
        self.assertAlmostEqual(report.mixed_miscoordination_probability, 25 / 49)
        self.assertAlmostEqual(report.mixed_expected_utilities.row, 12 / 7)
        self.assertAlmostEqual(report.mixed_expected_utilities.column, 12 / 7)

    def test_belief_and_compensation_thresholds_are_explicit(self) -> None:
        parameters = BattleOfTheSexesParameters()
        self.assertAlmostEqual(parameters.preferred_action_belief_threshold(), 3 / 7)
        self.assertAlmostEqual(
            parameters.preferred_action_belief_threshold(1.0), 4 / 9
        )
        report = battle_of_the_sexes_report()
        self.assertEqual(report.preference_advantage, 1.0)
        self.assertEqual(report.minimum_compensation_to_concede, 1.0)
        self.assertEqual(
            report.record()["threshold_kind"], "belief_in_preferred_coordination"
        )


if __name__ == "__main__":
    unittest.main()
