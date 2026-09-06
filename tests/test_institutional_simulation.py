import unittest

from utility_threshold.games import (
    ActionBelief,
    AsymmetricBeliefs,
    ContractPenalty,
    FixedInstitutionalStrategy,
    InstitutionalRules,
    MechanismStack,
    RiskAwareInstitutionalStrategy,
    TrustedMediator,
    autonomous_escalation_uncertainty,
    frontier_deployment_uncertainty,
    play_institutional_match,
)


class InstitutionalSimulationTests(unittest.TestCase):
    def test_contract_changes_decision_and_realizes_penalty_events(self) -> None:
        game = frontier_deployment_uncertainty()
        cooperative = game.cooperative_action
        prior = ActionBelief.binary(cooperative, game.competitive_action, 0.0)
        beliefs = AsymmetricBeliefs(prior, prior)
        rules = InstitutionalRules(
            stack=MechanismStack(
                payoff_mechanisms=(
                    ContractPenalty(
                        (cooperative, cooperative),
                        penalty=10.0,
                        deviation_detection_probability=1.0,
                        enforcement_probability=1.0,
                    ),
                )
            )
        )
        result = play_institutional_match(
            game,
            RiskAwareInstitutionalStrategy(),
            FixedInstitutionalStrategy("competitive"),
            rules=rules,
            rounds=1,
            initial_beliefs=beliefs,
            seed=4,
        )
        round_result = result.rounds[0]
        self.assertEqual(round_result.row_choice.action, cooperative)
        self.assertEqual(len(round_result.penalty_events), 2)
        self.assertTrue(round_result.penalty_events[1].enforced)
        self.assertEqual(round_result.penalties.column, 10.0)

    def test_monitoring_updates_private_beliefs_and_public_reputation(self) -> None:
        game = frontier_deployment_uncertainty()
        result = play_institutional_match(
            game,
            FixedInstitutionalStrategy("cooperative"),
            FixedInstitutionalStrategy("competitive"),
            rules=InstitutionalRules(
                monitoring_true_positive_rate=1.0,
                monitoring_false_positive_rate=0.0,
            ),
            rounds=2,
            seed=7,
        )
        first = result.rounds[0]
        self.assertEqual(len(first.monitoring_events), 2)
        self.assertAlmostEqual(
            first.beliefs_after.row_about_column.probability(game.competitive_action), 1.0
        )
        self.assertAlmostEqual(
            first.beliefs_after.column_about_row.probability(game.cooperative_action), 1.0
        )
        self.assertGreater(
            first.reputation_after.row.cooperation_probability,
            first.reputation_after.column.cooperation_probability,
        )

    def test_mediator_recommendations_produce_safe_anti_coordination(self) -> None:
        game = autonomous_escalation_uncertainty()
        mediator = TrustedMediator({
            (game.cooperative_action, game.competitive_action): 0.5,
            (game.competitive_action, game.cooperative_action): 0.5,
        })
        rules = InstitutionalRules(stack=MechanismStack(mediator=mediator))
        result = play_institutional_match(
            game,
            RiskAwareInstitutionalStrategy(follow_mediator=True),
            RiskAwareInstitutionalStrategy(follow_mediator=True),
            rules=rules,
            rounds=20,
            seed=11,
        )
        self.assertEqual(result.catastrophe_rate, 0.0)
        self.assertTrue(all(round_.row_choice.obeyed_mediator for round_ in result.rounds))
        self.assertTrue(all(round_.profile in mediator.distribution for round_ in result.rounds))

    def test_same_seed_reproduces_every_stochastic_event(self) -> None:
        game = autonomous_escalation_uncertainty()
        arguments = (
            game,
            FixedInstitutionalStrategy("competitive"),
            FixedInstitutionalStrategy("competitive"),
        )
        first = play_institutional_match(*arguments, rounds=8, seed=99)
        second = play_institutional_match(*arguments, rounds=8, seed=99)
        self.assertEqual(first.record(), second.record())

    def test_empirical_catastrophe_rate_tracks_latent_probability(self) -> None:
        game = autonomous_escalation_uncertainty()
        result = play_institutional_match(
            game,
            FixedInstitutionalStrategy("competitive"),
            FixedInstitutionalStrategy("competitive"),
            rounds=2000,
            seed=5,
        )
        self.assertAlmostEqual(result.catastrophe_rate, 0.45, delta=0.035)


if __name__ == "__main__":
    unittest.main()
