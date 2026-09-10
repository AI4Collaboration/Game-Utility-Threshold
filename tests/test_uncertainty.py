import math
import unittest

from utility_threshold.games import (
    ChickenParameters,
    BattleOfTheSexesParameters,
    DiscreteDistribution,
    Payoff,
    PayoffState,
    PrisonersDilemmaParameters,
    UncertainPayoffGame,
    WeightedOutcome,
    battle_of_the_sexes,
    chicken,
    prisoners_dilemma,
)


class DistributionTests(unittest.TestCase):
    def test_exact_distribution_statistics_and_tail_risk(self) -> None:
        distribution = DiscreteDistribution((
            WeightedOutcome("bad", 0.25, -10.0),
            WeightedOutcome("normal", 0.50, 2.0),
            WeightedOutcome("good", 0.25, 6.0),
        ))
        self.assertEqual(distribution.expected(), 0.0)
        self.assertEqual(distribution.variance(), 36.0)
        self.assertEqual(distribution.standard_deviation(), 6.0)
        self.assertEqual(distribution.quantile(0.25), -10.0)
        self.assertEqual(distribution.quantile(0.75), 2.0)
        self.assertEqual(distribution.lower_tail_cvar(0.25), -10.0)
        self.assertEqual(distribution.lower_tail_cvar(0.50), -4.0)
        self.assertAlmostEqual(distribution.entropy, 1.5 * math.log(2))
        self.assertEqual(distribution.probability(lambda value: value < 0), 0.25)

    def test_invalid_probability_mass_and_duplicate_labels_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DiscreteDistribution((WeightedOutcome("only", 0.9, 1.0),))
        with self.assertRaises(ValueError):
            DiscreteDistribution((
                WeightedOutcome("same", 0.5, 1.0),
                WeightedOutcome("same", 0.5, 2.0),
            ))


class UncertainPayoffGameTests(unittest.TestCase):
    def setUp(self) -> None:
        low = prisoners_dilemma(PrisonersDilemmaParameters(4.0, 3.0, 1.0, 0.0))
        high = prisoners_dilemma(PrisonersDilemmaParameters(6.0, 3.0, 1.0, -1.0))
        self.game = UncertainPayoffGame(
            game_id="uncertain_pd",
            name="Uncertain deployment race",
            states=(
                PayoffState("low_temptation", 0.25, low, parameters={"temptation": 4.0}),
                PayoffState("high_temptation", 0.75, high, parameters={"temptation": 6.0}),
            ),
        )

    def test_expected_game_is_probability_weighted(self) -> None:
        expected = self.game.expected_game()
        self.assertEqual(expected.payoff(("DEFECT", "COOPERATE")), Payoff(5.5, -0.75))
        self.assertEqual(self.game.expected_payoff(("COOPERATE", "DEFECT")), Payoff(-0.75, 5.5))
        self.assertEqual(expected.pure_nash_equilibria(), (("DEFECT", "DEFECT"),))

    def test_state_specific_payoff_distribution_is_preserved(self) -> None:
        distribution = self.game.payoff_distribution(("DEFECT", "COOPERATE"), "row")
        self.assertEqual(distribution.expected(), 5.5)
        self.assertEqual(distribution.quantile(0.25), 4.0)
        self.assertEqual([outcome.label for outcome in distribution.outcomes], [
            "low_temptation", "high_temptation"
        ])
        record = self.game.record()
        self.assertEqual(len(record["states"]), 2)
        self.assertEqual(len(record["expected_payoff_matrix"]), 4)

    def test_state_specific_catastrophe_probability(self) -> None:
        safe = chicken(ChickenParameters(catastrophe=-10.0))
        catastrophic = chicken(ChickenParameters(catastrophe=-30.0))
        uncertain = UncertainPayoffGame(
            "uncertain_chicken",
            "Uncertain escalation",
            (
                PayoffState("contained", 0.3, safe),
                PayoffState("catastrophic", 0.7, catastrophic),
            ),
        )
        self.assertEqual(uncertain.catastrophe_probability(("ESCALATE", "ESCALATE")), 1.0)
        self.assertEqual(uncertain.catastrophe_probability(("YIELD", "ESCALATE")), 0.0)

    def test_incompatible_game_forms_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            UncertainPayoffGame(
                "bad",
                "Bad",
                (
                    PayoffState("pd", 0.5, prisoners_dilemma()),
                    PayoffState("chicken", 0.5, chicken()),
                ),
            )

    def test_expected_game_supports_asymmetric_payoff_states(self) -> None:
        low = battle_of_the_sexes(BattleOfTheSexesParameters(4.0, 3.0, -1.0))
        high = battle_of_the_sexes(BattleOfTheSexesParameters(8.0, 5.0, -9.0))
        uncertain = UncertainPayoffGame(
            "uncertain_battle",
            "Uncertain protocol conflict",
            (
                PayoffState("low", 0.75, low),
                PayoffState("high", 0.25, high),
            ),
        )
        expected = uncertain.expected_game()
        self.assertFalse(expected.is_symmetric)
        self.assertEqual(expected.payoff(("OPTION_A", "OPTION_A")), Payoff(5.0, 3.5))
        self.assertEqual(expected.payoff(("OPTION_B", "OPTION_B")), Payoff(3.5, 5.0))


if __name__ == "__main__":
    unittest.main()
