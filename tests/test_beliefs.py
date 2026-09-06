import math
import unittest

from utility_threshold.games import (
    ActionBelief,
    AsymmetricBeliefs,
    BeliefTracker,
    SignalModel,
    binary_communication_model,
    imperfect_monitoring_model,
)


class BeliefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.actions = ("COOPERATE", "COMPETE")
        self.uniform = ActionBelief.binary(*self.actions, competitive_probability=0.5)

    def test_action_belief_is_normalized_and_auditable(self) -> None:
        self.assertEqual(self.uniform.probability("COMPETE"), 0.5)
        self.assertAlmostEqual(self.uniform.entropy, math.log(2))
        self.assertEqual(self.uniform.record()["probabilities"], {"COOPERATE": 0.5, "COMPETE": 0.5})
        with self.assertRaises(ValueError):
            ActionBelief(self.actions, {"COOPERATE": 0.2, "COMPETE": 0.2})

    def test_imperfect_monitoring_updates_by_bayes_rule(self) -> None:
        monitor = imperfect_monitoring_model(
            *self.actions,
            true_positive_rate=0.8,
            false_positive_rate=0.2,
        )
        update = monitor.observe(self.uniform, "SIGNAL_COMPETITIVE")
        self.assertAlmostEqual(update.posterior.probability("COMPETE"), 0.8)
        self.assertAlmostEqual(update.evidence_probability, 0.5)
        self.assertGreater(update.information_gain_nats, 0)
        self.assertGreater(update.record()["entropy_reduction_nats"], 0)

    def test_credible_communication_moves_beliefs_toward_claim(self) -> None:
        communication = binary_communication_model(*self.actions, credibility=0.9)
        cooperative_claim = communication.observe(self.uniform, "MESSAGE_COOPERATE")
        competitive_claim = communication.observe(self.uniform, "MESSAGE_COMPETE")
        self.assertAlmostEqual(cooperative_claim.posterior.probability("COOPERATE"), 0.9)
        self.assertAlmostEqual(competitive_claim.posterior.probability("COMPETE"), 0.9)

    def test_sequential_tracker_retains_every_update(self) -> None:
        message = binary_communication_model(*self.actions, credibility=0.75)
        monitor = imperfect_monitoring_model(*self.actions, true_positive_rate=0.9, false_positive_rate=0.1)
        tracker = BeliefTracker(self.uniform).observe_many((
            (message, "MESSAGE_COOPERATE"),
            (monitor, "SIGNAL_COMPETITIVE"),
        ))
        self.assertEqual(len(tracker.updates), 2)
        self.assertGreater(tracker.current.probability("COMPETE"), 0.5)
        self.assertEqual(len(tracker.record()["updates"]), 2)

    def test_asymmetric_beliefs_are_player_specific(self) -> None:
        asymmetric = AsymmetricBeliefs(
            row_about_column=ActionBelief.binary(*self.actions, competitive_probability=0.2),
            column_about_row=ActionBelief.binary(*self.actions, competitive_probability=0.8),
        )
        self.assertEqual(asymmetric.for_player("row").probability("COMPETE"), 0.2)
        self.assertEqual(asymmetric.for_player("column").probability("COMPETE"), 0.8)

    def test_zero_evidence_signal_is_rejected(self) -> None:
        impossible = SignalModel(
            actions=self.actions,
            signals=("POSSIBLE", "IMPOSSIBLE"),
            likelihoods={
                ("POSSIBLE", "COOPERATE"): 1.0,
                ("IMPOSSIBLE", "COOPERATE"): 0.0,
                ("POSSIBLE", "COMPETE"): 1.0,
                ("IMPOSSIBLE", "COMPETE"): 0.0,
            },
        )
        with self.assertRaises(ValueError):
            impossible.observe(self.uniform, "IMPOSSIBLE")


if __name__ == "__main__":
    unittest.main()
