import unittest

from run_phase_one_eval import aggregate_phase_one_records, selected_providers


class PhaseOneRunnerTests(unittest.TestCase):
    def test_provider_selection_is_ordered_and_unique(self) -> None:
        self.assertEqual(
            selected_providers(("google", "openai", "google")),
            ("google", "openai"),
        )
        with self.assertRaisesRegex(ValueError, "unknown providers"):
            selected_providers(("unknown",))

    def test_aggregation_preserves_research_strata(self) -> None:
        records = [
            {
                "provider": "openai",
                "design_stratum": "exact_boundary",
                "threshold_region": "boundary",
                "scores": {"optimal_action": 1, "utility_regret": 0.0},
            },
            {
                "provider": "anthropic",
                "design_stratum": "just_unsafe",
                "threshold_region": "unsafe",
                "scores": {"optimal_action": 0, "utility_regret": 0.25},
            },
        ]
        summary = aggregate_phase_one_records(records)
        self.assertEqual(summary["completed_samples"], 2)
        self.assertEqual(summary["overall"]["optimal_action"], 0.5)
        self.assertEqual(summary["by_provider"]["openai"]["samples"], 1)
        self.assertIn("exact_boundary", summary["by_design_stratum"])


if __name__ == "__main__":
    unittest.main()
