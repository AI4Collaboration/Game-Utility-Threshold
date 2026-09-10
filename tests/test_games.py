import unittest

from utility_threshold.games import (
    AUTONOMOUS_ESCALATION,
    FRONTIER_DEPLOYMENT_RACE,
    ChickenParameters,
    CompetitiveStrategy,
    CooperativeStrategy,
    ExpectedUtilityStrategy,
    InterventionPolicy,
    MixedNashStrategy,
    Payoff,
    PrisonersDilemmaParameters,
    RandomStrategy,
    SymmetricTwoByTwoGame,
    TwoByTwoGame,
    TitForTatStrategy,
    chicken,
    chicken_threshold_report,
    play_match,
    prisoners_dilemma,
    prisoners_dilemma_threshold_report,
    round_robin,
    threshold_sweep,
)


class NormalFormEngineTests(unittest.TestCase):
    def test_general_game_supports_asymmetric_mixed_equilibrium(self) -> None:
        game = TwoByTwoGame(
            game_id="battle",
            name="Battle of the Sexes",
            family="battle_of_the_sexes",
            actions=("A", "B"),
            cooperative_action="A",
            competitive_action="B",
            payoffs={
                ("A", "A"): Payoff(4, 3),
                ("A", "B"): Payoff(0, 0),
                ("B", "A"): Payoff(0, 0),
                ("B", "B"): Payoff(3, 4),
            },
        )
        self.assertFalse(game.is_symmetric)
        self.assertEqual(game.pure_nash_equilibria(), (("A", "A"), ("B", "B")))
        mixed = game.mixed_equilibrium()
        assert mixed is not None
        self.assertAlmostEqual(mixed["row"]["A"], 4 / 7)
        self.assertAlmostEqual(mixed["column"]["A"], 3 / 7)
        self.assertAlmostEqual(
            game.coordination_probability(mixed["row"], mixed["column"]),
            24 / 49,
        )
        self.assertIsNone(game.symmetric_mixed_equilibrium())

    def test_symmetric_subclass_retains_strict_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "not symmetric"):
            SymmetricTwoByTwoGame(
                game_id="bad",
                name="Bad",
                family="test",
                actions=("A", "B"),
                cooperative_action="A",
                competitive_action="B",
                payoffs={
                    ("A", "A"): Payoff(2, 1),
                    ("A", "B"): Payoff(0, 0),
                    ("B", "A"): Payoff(0, 0),
                    ("B", "B"): Payoff(1, 2),
                },
            )

    def test_matrix_validation_rejects_missing_and_asymmetric_payoffs(self) -> None:
        with self.assertRaises(ValueError):
            SymmetricTwoByTwoGame(
                game_id="bad",
                name="Bad",
                family="test",
                actions=("A", "B"),
                cooperative_action="A",
                competitive_action="B",
                payoffs={("A", "A"): Payoff(1, 1)},
            )
        with self.assertRaises(ValueError):
            SymmetricTwoByTwoGame(
                game_id="asymmetric",
                name="Asymmetric",
                family="test",
                actions=("A", "B"),
                cooperative_action="A",
                competitive_action="B",
                payoffs={
                    ("A", "A"): Payoff(1, 1),
                    ("A", "B"): Payoff(0, 2),
                    ("B", "A"): Payoff(3, 0),
                    ("B", "B"): Payoff(0, 0),
                },
            )

    def test_column_utilities_and_regret_use_column_perspective(self) -> None:
        game = prisoners_dilemma()
        self.assertEqual(game.action_utilities("column", "COOPERATE"), {"COOPERATE": 3.0, "DEFECT": 5.0})
        self.assertEqual(game.regret(("DEFECT", "COOPERATE"), "column"), 1.0)
        self.assertEqual(game.regret(("DEFECT", "COOPERATE"), "row"), 0.0)


class PrisonersDilemmaTests(unittest.TestCase):
    def test_base_game_has_dominant_defection_and_inefficient_equilibrium(self) -> None:
        game = prisoners_dilemma()
        self.assertEqual(game.dominant_actions("row", strict=True), ("DEFECT",))
        self.assertEqual(game.pure_nash_equilibria(), (("DEFECT", "DEFECT"),))
        self.assertEqual(game.welfare_optimal_profiles(), (("COOPERATE", "COOPERATE"),))
        self.assertNotIn(("DEFECT", "DEFECT"), game.pareto_efficient_profiles())

    def test_intervention_crosses_both_decision_thresholds(self) -> None:
        base = prisoners_dilemma_threshold_report(intervention=0.0)
        middle = prisoners_dilemma_threshold_report(intervention=1.5)
        boundary = prisoners_dilemma_threshold_report(intervention=2.0)
        safe = prisoners_dilemma_threshold_report(intervention=2.1)
        self.assertEqual(base.regime, "competition_dominant")
        self.assertEqual(middle.regime, "anti_coordination")
        self.assertIsNotNone(middle.symmetric_mixed_equilibrium)
        self.assertEqual(boundary.regime, "boundary")
        self.assertEqual(safe.regime, "cooperation_dominant")
        self.assertEqual(safe.pure_nash_equilibria, (("COOPERATE", "COOPERATE"),))
        self.assertEqual(base.minimum_intervention_for_cooperation_dominance, 2.0)

    def test_parameter_ordering_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            PrisonersDilemmaParameters(temptation=3, reward=5, punishment=1, sucker=0)


class ChickenTests(unittest.TestCase):
    def test_game_has_two_asymmetric_equilibria_and_one_mixed_equilibrium(self) -> None:
        game = chicken()
        self.assertEqual(
            game.pure_nash_equilibria(),
            (("YIELD", "ESCALATE"), ("ESCALATE", "YIELD")),
        )
        mixed = game.symmetric_mixed_equilibrium()
        self.assertIsNotNone(mixed)
        assert mixed is not None
        self.assertAlmostEqual(mixed["ESCALATE"], 1 / 12)
        self.assertAlmostEqual(game.catastrophe_probability(mixed, mixed), (1 / 12) ** 2)

    def test_mutual_escalation_is_an_explicit_catastrophe(self) -> None:
        game = chicken()
        self.assertIn(("ESCALATE", "ESCALATE"), game.catastrophic_profiles)
        self.assertEqual(game.payoff(("ESCALATE", "ESCALATE")), Payoff(-10.0, -10.0))
        self.assertGreater(game.regret(("ESCALATE", "ESCALATE"), "row"), 0)
        self.assertNotIn(("ESCALATE", "ESCALATE"), game.welfare_optimal_profiles("nash_product"))

    def test_intervention_eliminates_escalation_incentive(self) -> None:
        base = chicken_threshold_report(intervention=0.0)
        safe = chicken_threshold_report(intervention=1.1)
        self.assertEqual(base.regime, "anti_coordination")
        self.assertEqual(base.minimum_intervention_for_cooperation_dominance, 1.0)
        self.assertEqual(safe.regime, "cooperation_dominant")
        self.assertEqual(safe.pure_nash_equilibria, (("YIELD", "YIELD"),))

    def test_parameter_ordering_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            ChickenParameters(temptation=4, reward=3, sucker=-11, catastrophe=1)


class ScenarioAndSimulationTests(unittest.TestCase):
    def test_intervention_policy_decomposes_and_solves_enforcement_thresholds(self) -> None:
        policy = InterventionPolicy(
            direct_cost=0.25,
            detection_probability=0.5,
            sanction=2.0,
            internalized_harm=0.25,
        )
        self.assertEqual(policy.expected_cost, 1.5)
        self.assertEqual(policy.minimum_detection_probability(2.0), 0.75)
        self.assertEqual(policy.minimum_sanction(2.0), 3.0)
        self.assertEqual(FRONTIER_DEPLOYMENT_RACE.threshold_report(policy).regime, "anti_coordination")

    def test_scenarios_have_concrete_actions_and_correct_families(self) -> None:
        deployment = FRONTIER_DEPLOYMENT_RACE.game()
        escalation = AUTONOMOUS_ESCALATION.game()
        self.assertEqual(deployment.actions, ("PAUSE_FOR_AUDIT", "RACE_TO_DEPLOY"))
        self.assertEqual(deployment.family, "prisoners_dilemma")
        self.assertEqual(escalation.actions, ("DEESCALATE", "ESCALATE"))
        self.assertEqual(escalation.family, "chicken")
        self.assertIn(("ESCALATE", "ESCALATE"), escalation.catastrophic_profiles)

    def test_repeated_strategy_behavior_is_auditable(self) -> None:
        game = FRONTIER_DEPLOYMENT_RACE.game()
        result = play_match(game, TitForTatStrategy(), CompetitiveStrategy(), rounds=3, seed=7)
        self.assertEqual(
            [round_result.profile for round_result in result.rounds],
            [
                ("PAUSE_FOR_AUDIT", "RACE_TO_DEPLOY"),
                ("RACE_TO_DEPLOY", "RACE_TO_DEPLOY"),
                ("RACE_TO_DEPLOY", "RACE_TO_DEPLOY"),
            ],
        )
        self.assertEqual(result.row_total_utility, 2.0)
        self.assertEqual(result.column_total_utility, 7.0)

    def test_catastrophe_rate_and_seeded_randomness(self) -> None:
        game = AUTONOMOUS_ESCALATION.game()
        catastrophe = play_match(game, CompetitiveStrategy(), CompetitiveStrategy(), rounds=10)
        self.assertEqual(catastrophe.catastrophe_rate, 1.0)
        first = play_match(game, RandomStrategy(), RandomStrategy(), rounds=20, seed=11)
        second = play_match(game, RandomStrategy(), RandomStrategy(), rounds=20, seed=11)
        self.assertEqual(first.rounds, second.rounds)

    def test_round_robin_and_sweep_produce_research_records(self) -> None:
        game = FRONTIER_DEPLOYMENT_RACE.game()
        strategies = {
            "cooperate": CooperativeStrategy(),
            "compete": CompetitiveStrategy(),
            "best_response": ExpectedUtilityStrategy(),
            "mixed": MixedNashStrategy(),
        }
        tournament = round_robin(game, strategies, rounds=5, seed=4)
        self.assertEqual(len(tournament.matches), 16)
        self.assertEqual({row["strategy"] for row in tournament.leaderboard()}, set(strategies))
        points = threshold_sweep(FRONTIER_DEPLOYMENT_RACE, (0.0, 1.5, 2.1))
        self.assertEqual([point.report.regime for point in points], [
            "competition_dominant", "anti_coordination", "cooperation_dominant"
        ])


if __name__ == "__main__":
    unittest.main()
