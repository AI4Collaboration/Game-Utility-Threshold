import unittest

from run_model_gameplay import aggregate_gameplay_records, ordered_pairings


class ModelGameplayRunnerTests(unittest.TestCase):
    def test_ordered_pairings_include_self_and_both_cross_play_orders(self) -> None:
        self.assertEqual(
            ordered_pairings(("openai", "anthropic")),
            (
                ("openai", "openai"),
                ("openai", "anthropic"),
                ("anthropic", "openai"),
                ("anthropic", "anthropic"),
            ),
        )

    def test_aggregates_cover_treatment_scenario_pair_and_model(self) -> None:
        records = [
            {
                "row_provider": "openai",
                "column_provider": "anthropic",
                "scenario_id": "frontier_deployment_race",
                "treatment": "baseline",
                "objective": "individual_expected_utility",
                "cooperative_action": "SAFE",
                "scores": {"cooperative_action_rate": 0.5, "expected_welfare": 2.0},
                "joint_outcome": {
                    "valid_joint_action": True,
                    "profile": ["SAFE", "RACE"],
                    "row_expected_regret": 1.0,
                    "column_expected_regret": 0.0,
                },
            },
            {
                "row_provider": "anthropic",
                "column_provider": "openai",
                "scenario_id": "autonomous_escalation",
                "treatment": "mediator",
                "objective": "individual_expected_utility",
                "cooperative_action": "SAFE",
                "scores": {"cooperative_action_rate": 1.0, "expected_welfare": 4.0},
                "joint_outcome": {
                    "valid_joint_action": True,
                    "profile": ["SAFE", "SAFE"],
                    "row_expected_regret": 0.0,
                    "column_expected_regret": 0.0,
                },
            },
        ]
        summary = aggregate_gameplay_records(records)
        self.assertEqual(summary["completed_joint_games"], 2)
        self.assertAlmostEqual(summary["overall"]["expected_welfare"], 3.0)
        self.assertEqual(len(summary["by_treatment"]), 2)
        self.assertEqual(summary["by_model_across_roles"]["openai"]["decision_count"], 2)
        self.assertIn("first_action_rate", summary["by_model_across_roles"]["openai"])


if __name__ == "__main__":
    unittest.main()
