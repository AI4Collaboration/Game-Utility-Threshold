import unittest

from utility_threshold.games import (
    ActionBelief,
    AsymmetricBeliefs,
    BetaReputation,
    BindingCommitment,
    ContractPenalty,
    MechanismStack,
    NonBindingCommunication,
    ReputationEvidence,
    ReputationLedger,
    TrustedMediator,
    chicken,
    fair_welfare_mediator,
    prisoners_dilemma,
)


class CommunicationAndReputationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = prisoners_dilemma()
        neutral = ActionBelief.binary(
            self.game.cooperative_action,
            self.game.competitive_action,
            competitive_probability=0.5,
        )
        self.priors = AsymmetricBeliefs(neutral, neutral)

    def test_simultaneous_cheap_talk_creates_asymmetric_posteriors(self) -> None:
        communication = NonBindingCommunication(
            row_message=self.game.cooperative_action,
            column_message=self.game.competitive_action,
            row_credibility=0.9,
            column_credibility=0.8,
        )
        outcome = communication.run(self.priors)
        self.assertAlmostEqual(
            outcome.posteriors.row_about_column.probability(self.game.competitive_action),
            0.8,
        )
        self.assertAlmostEqual(
            outcome.posteriors.column_about_row.probability(self.game.cooperative_action),
            0.9,
        )
        self.assertFalse(outcome.record()["binding"])

    def test_reputation_accumulates_soft_evidence_with_decay(self) -> None:
        reputation = BetaReputation(decay=0.5)
        first = reputation.update(ReputationEvidence(0, cooperative_probability=1.0, weight=2.0))
        second = first.update(ReputationEvidence(1, cooperative_probability=0.0, weight=1.0))
        self.assertEqual((first.alpha, first.beta), (3.0, 1.0))
        self.assertEqual((second.alpha, second.beta), (2.0, 2.0))
        self.assertEqual(len(second.evidence), 2)
        self.assertAlmostEqual(second.cooperation_probability, 0.5)

    def test_ledger_turns_subject_reputation_into_opponent_beliefs(self) -> None:
        ledger = ReputationLedger().update(
            "column", ReputationEvidence(0, cooperative_probability=1.0, weight=3.0)
        )
        beliefs = ledger.asymmetric_beliefs(self.game)
        self.assertAlmostEqual(
            beliefs.row_about_column.probability(self.game.cooperative_action), 0.8
        )
        self.assertAlmostEqual(
            beliefs.column_about_row.probability(self.game.cooperative_action), 0.5
        )


class MediatorAndCompositionTests(unittest.TestCase):
    def test_fair_chicken_mediator_is_incentive_compatible(self) -> None:
        game = chicken()
        mediator = TrustedMediator(
            {
                (game.cooperative_action, game.competitive_action): 0.5,
                (game.competitive_action, game.cooperative_action): 0.5,
            },
            objective="fair_anti_coordination",
        )
        analysis = mediator.analyze(game)
        self.assertTrue(analysis.is_correlated_equilibrium)
        self.assertEqual(len(analysis.constraints), 4)
        self.assertGreaterEqual(min(item.obedience_margin for item in analysis.constraints), 1.0)
        self.assertEqual(mediator.draw(seed=2).profile, (game.competitive_action, game.cooperative_action))

    def test_welfare_mediator_discloses_when_recommendation_is_not_stable(self) -> None:
        game = prisoners_dilemma()
        analysis = fair_welfare_mediator(game).analyze(game)
        self.assertFalse(analysis.is_correlated_equilibrium)
        self.assertAlmostEqual(analysis.maximum_deviation_gain, 2.0)

    def test_stack_composes_every_institutional_layer(self) -> None:
        game = prisoners_dilemma()
        neutral = ActionBelief.binary(
            game.cooperative_action, game.competitive_action, competitive_probability=0.5
        )
        priors = AsymmetricBeliefs(neutral, neutral)
        mediator = TrustedMediator({(game.cooperative_action, game.cooperative_action): 1.0})
        stack = MechanismStack(
            payoff_mechanisms=(
                ContractPenalty((game.cooperative_action, game.cooperative_action), penalty=3.0),
                BindingCommitment(row_action=game.cooperative_action),
            ),
            communication=NonBindingCommunication(
                game.cooperative_action, game.cooperative_action
            ),
            mediator=mediator,
        )
        environment = stack.apply(game, priors=priors, reputation=ReputationLedger())
        record = environment.record()
        self.assertEqual(len(record["adjusted_game"]["mechanism_trace"]), 2)
        self.assertIsNotNone(record["communication"])
        self.assertTrue(record["mediation"]["is_correlated_equilibrium"])
        self.assertIsNotNone(record["reputation"])

    def test_communication_requires_explicit_priors(self) -> None:
        game = prisoners_dilemma()
        with self.assertRaises(ValueError):
            MechanismStack(
                communication=NonBindingCommunication(
                    game.cooperative_action, game.cooperative_action
                )
            ).apply(game)


if __name__ == "__main__":
    unittest.main()
