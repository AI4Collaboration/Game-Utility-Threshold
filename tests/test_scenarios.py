import json
import unittest

from utility_threshold.games import (
    BattleOfTheSexesReport,
    SCENARIOS,
    UtilityThresholdReport,
    scenario_from_id,
)


class CanonicalScenarioTests(unittest.TestCase):
    def test_registry_contains_four_distinct_strategic_families(self) -> None:
        self.assertEqual(
            {scenario.family for scenario in SCENARIOS.values()},
            {
                "prisoners_dilemma",
                "chicken",
                "stag_hunt",
                "battle_of_the_sexes",
            },
        )

    def test_stag_hunt_scenario_exposes_assurance_failure(self) -> None:
        scenario = scenario_from_id("cross_lab_incident_response")
        game = scenario.game()
        self.assertTrue(game.is_symmetric)
        self.assertEqual(
            set(game.pure_nash_equilibria()),
            {
                ("JOINT_CONTAINMENT", "JOINT_CONTAINMENT"),
                ("LOCAL_LOCKDOWN", "LOCAL_LOCKDOWN"),
            },
        )
        self.assertEqual(set(game.catastrophic_profiles), set(game.miscoordination_profiles))
        report = scenario.threshold_report()
        self.assertIsInstance(report, UtilityThresholdReport)
        self.assertEqual(report.minimum_intervention_for_cooperation_dominance, 2.0)
        self.assertAlmostEqual(report.mixed_catastrophe_probability, 4.0 / 9.0)

    def test_battle_scenario_preserves_opposed_focal_preferences(self) -> None:
        scenario = scenario_from_id("incident_response_protocol")
        game = scenario.game()
        self.assertFalse(game.is_symmetric)
        self.assertEqual(set(game.pure_nash_equilibria()), set(game.coordination_profiles))
        self.assertGreater(
            game.payoff(game.coordination_profiles[0]).row,
            game.payoff(game.coordination_profiles[1]).row,
        )
        self.assertGreater(
            game.payoff(game.coordination_profiles[1]).column,
            game.payoff(game.coordination_profiles[0]).column,
        )
        report = scenario.threshold_report()
        self.assertIsInstance(report, BattleOfTheSexesReport)
        self.assertAlmostEqual(report.mixed_coordination_probability, 264.0 / 529.0)
        self.assertAlmostEqual(report.mixed_miscoordination_probability, 265.0 / 529.0)
        self.assertAlmostEqual(
            report.mixed_catastrophe_probability,
            report.mixed_miscoordination_probability,
        )

    def test_every_scenario_record_and_threshold_report_are_json_serializable(self) -> None:
        for scenario in SCENARIOS.values():
            json.dumps(scenario.record())
            json.dumps(scenario.threshold_report().record())


if __name__ == "__main__":
    unittest.main()
