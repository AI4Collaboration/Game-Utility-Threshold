import unittest

from utility_threshold.games import (
    StagHuntParameters,
    stag_hunt,
    stag_hunt_threshold_report,
)


class StagHuntTests(unittest.TestCase):
    def test_parameter_ordering_is_strict(self) -> None:
        with self.assertRaisesRegex(ValueError, "Stag Hunt requires"):
            StagHuntParameters(
                mutual_cooperation=3,
                safe_against_cooperation=3,
                mutual_safety=2,
                failed_cooperation=0,
            )

    def test_baseline_has_payoff_and_risk_dominant_equilibria(self) -> None:
        game = stag_hunt()
        self.assertEqual(
            game.pure_nash_equilibria(),
            (("COOPERATE", "COOPERATE"), ("SAFE", "SAFE")),
        )
        self.assertEqual(
            game.welfare_optimal_profiles(), (("COOPERATE", "COOPERATE"),)
        )
        self.assertEqual(game.pareto_efficient_profiles(), (("COOPERATE", "COOPERATE"),))
        mixed = game.symmetric_mixed_equilibrium()
        assert mixed is not None
        self.assertAlmostEqual(mixed["COOPERATE"], 2 / 3)
        self.assertEqual(
            StagHuntParameters().risk_dominant_action(), "SAFE"
        )

    def test_assurance_threshold_and_subsidy_are_exact(self) -> None:
        parameters = StagHuntParameters()
        self.assertAlmostEqual(parameters.assurance_threshold(), 2 / 3)
        self.assertAlmostEqual(parameters.assurance_threshold(1.0), 1 / 3)
        self.assertEqual(parameters.risk_dominant_action(cooperation_subsidy=1.0), "COOPERATE")

        report = stag_hunt_threshold_report()
        self.assertAlmostEqual(report.assurance_belief_threshold, 2 / 3)
        self.assertAlmostEqual(report.risk_dominance_margin, -1 / 6)
        self.assertEqual(report.payoff_dominant_profile, ("COOPERATE", "COOPERATE"))
        self.assertEqual(report.risk_dominant_profile, ("SAFE", "SAFE"))
        self.assertAlmostEqual(report.mixed_miscoordination_probability, 4 / 9)
        self.assertEqual(
            report.record()["threshold_kind"],
            "assurance_belief_and_action_incentive",
        )

    def test_intervention_crosses_cooperation_dominance_boundary(self) -> None:
        boundary = stag_hunt_threshold_report(intervention=2.0)
        self.assertEqual(boundary.regime, "boundary")
        self.assertEqual(
            stag_hunt(intervention=2.0).dominant_actions("row"), ("COOPERATE",)
        )
        self.assertIn(("SAFE", "SAFE"), boundary.pure_nash_equilibria)
        above = stag_hunt_threshold_report(intervention=2.01)
        self.assertTrue(above.cooperation_is_strictly_dominant)
        self.assertEqual(above.pure_nash_equilibria, (("COOPERATE", "COOPERATE"),))


if __name__ == "__main__":
    unittest.main()
