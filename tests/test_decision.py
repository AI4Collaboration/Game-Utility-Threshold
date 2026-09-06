import unittest

from utility_threshold.games import (
    ActionBelief,
    AmbiguousActionBelief,
    CARACriterion,
    ChickenParameters,
    ExpectedValueCriterion,
    LowerCVaRCriterion,
    MaximinCriterion,
    MeanVarianceCriterion,
    PayoffState,
    PrisonersDilemmaParameters,
    ProspectValueCriterion,
    StateActionBelief,
    UncertainPayoffGame,
    analyze_ambiguity,
    analyze_decision,
    chicken,
    prisoners_dilemma,
    solve_risk_adjusted_threshold,
)


def uncertain_pd() -> UncertainPayoffGame:
    return UncertainPayoffGame(
        "uncertain_pd",
        "Uncertain deployment race",
        (
            PayoffState(
                "low",
                0.25,
                prisoners_dilemma(PrisonersDilemmaParameters(4.0, 3.0, 1.0, 0.0)),
            ),
            PayoffState(
                "high",
                0.75,
                prisoners_dilemma(PrisonersDilemmaParameters(6.0, 3.0, 1.0, -1.0)),
            ),
        ),
    )


def uncertain_chicken() -> UncertainPayoffGame:
    return UncertainPayoffGame(
        "uncertain_chicken",
        "Uncertain escalation",
        (
            PayoffState("contained", 0.5, chicken(ChickenParameters(5.0, 3.0, 1.0, -10.0))),
            PayoffState("catastrophic", 0.5, chicken(ChickenParameters(5.0, 3.0, 1.0, -30.0))),
        ),
    )


class RiskDecisionTests(unittest.TestCase):
    def test_expected_value_analysis_retains_every_world_outcome(self) -> None:
        game = uncertain_pd()
        belief = ActionBelief.binary(*game.actions, competitive_probability=0.5)
        analysis = analyze_decision(game, "row", belief)
        self.assertEqual(len(analysis.lotteries[game.cooperative_action].outcomes), 4)
        self.assertAlmostEqual(analysis.evaluations[game.cooperative_action].expected_utility, 1.125)
        self.assertAlmostEqual(analysis.evaluations[game.competitive_action].expected_utility, 3.25)
        self.assertEqual(analysis.selected_action, game.competitive_action)
        self.assertAlmostEqual(analysis.safe_action_margin, -2.125)
        self.assertEqual(len(analysis.record()["lotteries"][game.cooperative_action]), 4)

    def test_risk_attitudes_can_change_escalation_choice(self) -> None:
        game = uncertain_chicken()
        belief = ActionBelief.binary(*game.actions, competitive_probability=0.05)
        expected = analyze_decision(game, "row", belief, ExpectedValueCriterion())
        cara = analyze_decision(game, "row", belief, CARACriterion(risk_aversion=0.2))
        cvar = analyze_decision(game, "row", belief, LowerCVaRCriterion(alpha=0.1))
        maximin = analyze_decision(game, "row", belief, MaximinCriterion())
        self.assertEqual(expected.selected_action, game.competitive_action)
        self.assertEqual(cara.selected_action, game.cooperative_action)
        self.assertEqual(cvar.selected_action, game.cooperative_action)
        self.assertEqual(maximin.selected_action, game.cooperative_action)
        self.assertEqual(expected.catastrophe_probabilities[game.competitive_action], 0.05)

    def test_mean_variance_and_prospect_criteria_emit_full_summaries(self) -> None:
        game = uncertain_chicken()
        belief = ActionBelief.binary(*game.actions, competitive_probability=0.1)
        for criterion in (MeanVarianceCriterion(0.05), ProspectValueCriterion(reference_point=2.0)):
            analysis = analyze_decision(game, "column", belief, criterion)
            evaluation = analysis.evaluations[game.competitive_action]
            self.assertEqual(evaluation.criterion, criterion.name)
            self.assertGreaterEqual(evaluation.variance, 0)
            self.assertIn("parameters", evaluation.record())

    def test_correlated_state_action_belief_overrides_independence(self) -> None:
        game = uncertain_pd()
        joint = StateActionBelief(
            state_ids=("low", "high"),
            actions=game.actions,
            probabilities={
                ("low", game.cooperative_action): 0.25,
                ("low", game.competitive_action): 0.0,
                ("high", game.cooperative_action): 0.0,
                ("high", game.competitive_action): 0.75,
            },
        )
        placeholder = ActionBelief.binary(*game.actions, competitive_probability=0.5)
        analysis = analyze_decision(game, "row", placeholder, joint_belief=joint)
        self.assertEqual(analysis.opponent_belief.probability(game.competitive_action), 0.75)
        self.assertEqual(joint.state_marginal(), {"low": 0.25, "high": 0.75})

    def test_ambiguity_uses_worst_case_action_belief(self) -> None:
        game = uncertain_chicken()
        ambiguity = AmbiguousActionBelief(*game.actions, 0.0, 0.1)
        robust = analyze_ambiguity(game, "row", ambiguity)
        self.assertEqual(robust.selected_action, game.cooperative_action)
        self.assertGreater(robust.robust_safe_action_margin, 0)
        self.assertEqual(len(robust.endpoint_analyses), 2)

    def test_risk_adjusted_threshold_is_solved_numerically(self) -> None:
        game = uncertain_pd()
        belief = ActionBelief.binary(*game.actions, competitive_probability=0.0)
        threshold = solve_risk_adjusted_threshold(game, "row", belief, max_cost=5.0)
        self.assertTrue(threshold.feasible)
        self.assertAlmostEqual(threshold.threshold or 0.0, 2.5, places=5)
        self.assertGreater(threshold.iterations, 0)
        self.assertEqual(threshold.criterion, "expected_value")


if __name__ == "__main__":
    unittest.main()
